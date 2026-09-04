# ==========================================================
# Quiz lifecycle + authoritative server-side scoring.
#
# A QuizStore owns the authoritative session state. Quizzes and
# attempts are persisted as JSON (mirroring the uploads/index.json
# pattern) so they survive across process restarts; the grading is
# ALWAYS recomputed server-side from the stored correct answers.
# Client-submitted answers, scores and correctness are never trusted.
# ==========================================================

import json
import os
import time
import uuid

from src.config import QUIZ_STORE_DIR
from src.quizzes.models import (
    Attempt,
    AttemptStatus,
    GenerationStatus,
    OPTION_LETTERS,
    Quiz,
)


def _now():
    return time.time()


class QuizNotFoundError(Exception):
    pass


class QuizStore:
    """
    Persistent store for quiz definitions and attempts.

    Layout:
        QUIZ_STORE_DIR/
            index.json   -> { "quizzes": {...}, "attempts": {...} }
    """

    def __init__(self, directory=None):
        self.directory = directory or QUIZ_STORE_DIR
        self._index_path = os.path.join(self.directory, "index.json")
        self._index = {"quizzes": {}, "attempts": {}}
        self._load()

    # ----------------------------------------------------
    # persistence helpers
    # ----------------------------------------------------

    def _load(self):
        if os.path.exists(self._index_path):
            try:
                with open(self._index_path, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                self._index["quizzes"] = raw.get("quizzes", {})
                self._index["attempts"] = raw.get("attempts", {})
            except (json.JSONDecodeError, OSError):
                self._index = {"quizzes": {}, "attempts": {}}

    def _flush(self):
        os.makedirs(self.directory, exist_ok=True)
        tmp = self._index_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self._index, fh, indent=2, sort_keys=False)
        os.replace(tmp, self._index_path)

    # ----------------------------------------------------
    # quiz registry
    # ----------------------------------------------------

    def save_quiz(self, quiz):
        self._index["quizzes"][quiz.id] = quiz.to_dict()
        self._flush()
        return quiz

    def get_quiz(self, quiz_id):
        data = self._index["quizzes"].get(quiz_id)
        if data is None:
            raise QuizNotFoundError(
                f"quiz {quiz_id} not found"
            )
        return Quiz.from_dict(data)

    def delete_quiz(self, quiz_id):
        existed = self._index["quizzes"].pop(quiz_id, None)
        # Remove any attempts belonging to this quiz.
        self._index["attempts"] = {
            aid: att
            for aid, att in self._index["attempts"].items()
            if att.get("quiz_id") != quiz_id
        }
        self._flush()
        return existed is not None

    def list_quizzes(self):
        return [
            Quiz.from_dict(data)
            for data in self._index["quizzes"].values()
        ]

    # ----------------------------------------------------
    # attempt lifecycle
    # ----------------------------------------------------

    def save_attempt(self, attempt):
        self._index["attempts"][attempt.id] = attempt.to_dict()
        self._flush()
        return attempt

    def get_attempt(self, attempt_id):
        data = self._index["attempts"].get(attempt_id)
        if data is None:
            raise QuizNotFoundError(
                f"attempt {attempt_id} not found"
            )
        return Attempt.from_dict(data)

    # ----------------------------------------------------
    # session operations
    # ----------------------------------------------------

    def create_attempt(self, quiz):
        attempt = Attempt(
            id=str(uuid.uuid4()),
            quiz_id=quiz.id,
            status=AttemptStatus.CREATED.value,
            created_at=_now(),
        )
        return self.save_attempt(attempt)

    def start_attempt(self, attempt):
        quiz = self.get_quiz(attempt.quiz_id)
        if attempt.quiz_id != quiz.id:
            raise QuizNotFoundError("quiz/attempt mismatch")
        attempt.started_at = _now()
        attempt.status = AttemptStatus.STARTED.value
        return self.save_attempt(attempt)

    def cancel_attempt(self, attempt_id):
        attempt = self.get_attempt(attempt_id)
        attempt.submitted_at = _now()
        attempt.result_status = "CANCELLED"
        return self.save_attempt(attempt)

    # ----------------------------------------------------
    # authoritative scoring
    # ----------------------------------------------------

    def grade(self, quiz, attempt, submitted_answers):
        """
        Recompute correctness server-side from the stored
        authoritative answers. `submitted_answers` maps question_id
        -> option letter chosen by the client.

        Result: (attempt, summary_dict). The returned Attempt carries:
          * score / total / correct map,
          * result_status COMPLETED (all answered) or PARTIAL (some
            unanswered, with a structured reason),
          * timed_out flag from the server-side timer.
        """
        total = len(quiz.questions)
        answers = {}
        correct = {}
        answered_count = 0
        unanswered = []

        for q in quiz.questions:
            chosen = (submitted_answers or {}).get(q.id)

            # The authoritative check compares the chosen letter to the
            # stored correct letter. Anything else (missing or wrong
            # letter) is incorrect.
            if chosen is not None:
                chosen = str(chosen).strip().upper()
                answers[q.id] = chosen
                is_correct = chosen == q.correct_letter
                answered_count += 1
            else:
                answers[q.id] = None
                is_correct = False
                unanswered.append(q.id)

            correct[q.id] = is_correct

        score = sum(1 for v in correct.values() if v)

        # Timer logic (docker-free): record the delta server-side.
        elapsed = None
        timed_out = False
        started_at = attempt.started_at
        submitted_at = _now()
        if started_at:
            elapsed = submitted_at - started_at
        if quiz.time_limit_seconds and quiz.time_limit_seconds > 0:
            if elapsed is not None and elapsed > quiz.time_limit_seconds:
                timed_out = True

        attempt.answers = answers
        attempt.submitted_at = submitted_at
        attempt.score = score
        attempt.total = total
        attempt.correct = correct
        attempt.timed_out = timed_out

        if answered_count == total:
            attempt.result_status = "COMPLETED"
            attempt.partial_reason = ""
        else:
            attempt.result_status = "PARTIAL"
            attempt.partial_reason = (
                f"{total - answered_count} of {total} questions unanswered: "
                + ", ".join(unanswered)
            )

        attempt.status = AttemptStatus.SUBMITTED.value

        self.save_attempt(attempt)

        summary = {
            "score": score,
            "total": total,
            "answered": answered_count,
            "unanswered": unanswered,
            "result_status": attempt.result_status,
            "partial_reason": attempt.partial_reason,
            "timed_out": timed_out,
            "elapsed_seconds": (round(elapsed, 3) if elapsed is not None else None),
            "submitted_at": submitted_at,
        }

        # Per-question correctness is exposed keyed by question id for
        # the client to render.
        summary["correct"] = {
            qid: bool(v) for qid, v in correct.items()
        }

        return attempt, summary
