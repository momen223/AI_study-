# ==========================================================
# Quiz REST API (backend only, MCQ).
#
#   POST   /api/quizzes           generate a quiz for a library
#   GET    /api/quizzes/<id>      quiz metadata + questions (no answers)
#   POST   /api/quizzes/<id>/start  begin an attempt (starts timer)
#   POST   /api/quizzes/<id>/submit submit answers -> authoritative score
#   GET    /api/quizzes/<id>/result graded result for an attempt
#   DELETE /api/quizzes/<id>      remove a quiz
#
# Security properties:
#   * The correct answer is stored server-side and is NEVER returned
#     to the client before submission.
#   * Scoring is recomputed server-side; client answers are the only
#     untrusted input.
#   * Errors surface structured, client-safe reasons only (no stack
#     traces, no raw provider internals beyond a sanitized reason).
# ==========================================================

from flask import Blueprint, jsonify, request
from src.config import (
    QUIZ_MAX_QUESTION_COUNT,
    QUIZ_ALLOWED_DIFFICULTIES,
    QUIZ_DEFAULT_QUESTION_COUNT,
    QUIZ_DEFAULT_TIME_LIMIT_SECONDS,
)
from api import libraries as libs
from src.quizzes.lifecycle import QuizStore, QuizNotFoundError
from src.quizzes.generation import generate_quiz, QuizGenerationError
from src.quizzes.models import AttemptStatus

quiz_bp = Blueprint("quizzes", __name__)

_store = QuizStore()


def _library_store(library_id):
    """Return (vectorstore, subject, collection) or raise ValueError."""
    collection, persist = libs.get_library(library_id)
    if not collection or not persist:
        raise ValueError("unknown library")
    store = libs.load_store(collection, persist)
    subject = collection.replace("_", " ").title()
    return store, subject, collection


def _validate_create_payload(body):
    """Normalize + validate the create-quiz body. Raises ValueError."""
    library_id = body.get("library") or body.get("library_id")
    if not library_id:
        raise ValueError("library is required")

    count = body.get("question_count", QUIZ_DEFAULT_QUESTION_COUNT)
    try:
        count = int(count)
    except (TypeError, ValueError):
        raise ValueError("question_count must be an integer")

    if count < 1:
        raise ValueError("question_count must be at least 1")
    if count > QUIZ_MAX_QUESTION_COUNT:
        raise ValueError(
            f"question_count exceeds maximum {QUIZ_MAX_QUESTION_COUNT}"
        )

    difficulty = body.get("difficulty", "mixed") or "mixed"
    difficulty = str(difficulty).strip().lower()
    if difficulty not in QUIZ_ALLOWED_DIFFICULTIES:
        raise ValueError(
            f"difficulty must be one of {', '.join(QUIZ_ALLOWED_DIFFICULTIES)}"
        )

    topic = (body.get("topic") or "").strip() or None

    tls_raw = body.get("time_limit_seconds",
                       QUIZ_DEFAULT_TIME_LIMIT_SECONDS)
    try:
        tls = int(tls_raw)
    except (TypeError, ValueError):
        raise ValueError("time_limit_seconds must be an integer")
    if tls < 0:
        raise ValueError("time_limit_seconds must be >= 0")

    return {
        "library_id": library_id,
        "count": count,
        "difficulty": difficulty,
        "topic": topic,
        "time_limit_seconds": tls,
    }


def _subject_name(collection):
    return collection.replace("_", " ").title()


@quiz_bp.route("/api/quizzes", methods=["POST"])
def create_quiz():
    body = request.get_json(silent=True) or {}
    try:
        payload = _validate_create_payload(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        store, collection, _ = _library_store(payload["library_id"])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": "failed to load library"}), 422

    topic = payload["topic"] or _subject_name(collection)

    try:
        quiz = generate_quiz(
            vectorstore=store,
            library_id=payload["library_id"],
            subject=_subject_name(collection),
            topic=topic,
            question_count=payload["count"],
            difficulty=payload["difficulty"],
            time_limit_seconds=payload["time_limit_seconds"],
        )
    except QuizGenerationError as exc:
        return jsonify({"error": exc.reason}), 422

    _store.save_quiz(quiz)

    return jsonify({"quiz": quiz.public_dict()}), 201


@quiz_bp.route("/api/quizzes/<quiz_id>", methods=["GET"])
def get_quiz(quiz_id):
    try:
        quiz = _store.get_quiz(quiz_id)
    except QuizNotFoundError:
        return jsonify({"error": "quiz not found"}), 404
    return jsonify({"quiz": quiz.public_dict()})


@quiz_bp.route("/api/quizzes/<quiz_id>", methods=["DELETE"])
def delete_quiz(quiz_id):
    existed = _store.delete_quiz(quiz_id)
    if not existed:
        return jsonify({"error": "quiz not found"}), 404
    return jsonify({"deleted": quiz_id})


@quiz_bp.route("/api/quizzes/<quiz_id>/start", methods=["POST"])
def start_quiz(quiz_id):
    try:
        quiz = _store.get_quiz(quiz_id)
    except QuizNotFoundError:
        return jsonify({"error": "quiz not found"}), 404

    # Reuse an existing not-yet-submitted attempt if present.
    attempt = None
    for att in _store._index["attempts"].values():
        if (
            att.get("quiz_id") == quiz_id
            and att.get("status") != AttemptStatus.SUBMITTED.value
        ):
            attempt = _store.get_attempt(att["id"])
            break

    if attempt is None:
        attempt = _store.create_attempt(quiz)

    if attempt.status != AttemptStatus.STARTED.value:
        attempt = _store.start_attempt(attempt)

    payload = quiz.public_dict(reveal_answers=False)
    payload["attempt_id"] = attempt.id
    payload["started_at"] = attempt.started_at

    return jsonify(payload)


@quiz_bp.route("/api/quizzes/<quiz_id>/submit", methods=["POST"])
def submit_quiz(quiz_id):
    try:
        quiz = _store.get_quiz(quiz_id)
    except QuizNotFoundError:
        return jsonify({"error": "quiz not found"}), 404

    body = request.get_json(silent=True) or {}
    attempt_id = body.get("attempt_id")
    if not attempt_id:
        return jsonify({"error": "attempt_id is required"}), 400

    try:
        attempt = _store.get_attempt(attempt_id)
    except QuizNotFoundError:
        return jsonify({"error": "attempt not found"}), 404

    if attempt.quiz_id != quiz.id:
        return jsonify({"error": "attempt/quiz mismatch"}), 400

    if attempt.status == AttemptStatus.SUBMITTED.value:
        # Already graded: idempotently return the stored result.
        stored = _store.get_attempt(attempt.id)
        quiz_payload = quiz.public_dict(reveal_answers=True)
        return jsonify({
            "quiz": quiz_payload,
            "attempt": stored.to_dict(),
            "result": stored.result_status,
            "score": {
                "score": stored.score,
                "total": stored.total,
                "answered": sum(1 for v in stored.correct.values() if v is not None),
                "correct": stored.correct,
            },
        })

    answers = body.get("answers") or {}
    if not isinstance(answers, dict):
        return jsonify({"error": "answers must be an object"}), 400

    graded, summary = _store.grade(quiz, attempt, answers)

    return jsonify({
        "quiz": quiz.public_dict(reveal_answers=True),
        "attempt": graded.to_dict(),
        "result": graded.result_status,
        "score": summary,
    })


@quiz_bp.route("/api/quizzes/<quiz_id>/result", methods=["GET"])
def quiz_result(quiz_id):
    try:
        quiz = _store.get_quiz(quiz_id)
    except QuizNotFoundError:
        return jsonify({"error": "quiz not found"}), 404

    attempt_id = request.args.get("attempt_id")
    if not attempt_id:
        return jsonify({"error": "attempt_id query parameter is required"}), 400
    try:
        attempt = _store.get_attempt(attempt_id)
    except QuizNotFoundError:
        return jsonify({"error": "attempt not found"}), 404
    if attempt.quiz_id != quiz.id:
        return jsonify({"error": "attempt/quiz mismatch"}), 400
    if attempt.status != AttemptStatus.SUBMITTED.value:
        return jsonify({"error": "attempt has not been submitted"}), 409

    return jsonify({
        "quiz": quiz.public_dict(reveal_answers=True),
        "attempt": attempt.to_dict(),
        "result": attempt.result_status,
        "score": {
            "score": attempt.score,
            "total": attempt.total,
            "answered": sum(1 for v in attempt.correct.values() if v is not None),
            "correct": attempt.correct,
        },
    })
