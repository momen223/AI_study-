# ==========================================================
# Quiz data model + status constants.
#
# A quiz is a set of MCQ items generated from a library's
# corpus. The authoritative correctness (correct option) is
# stored server-side and is NEVER trusted from the client.
#
# Two distinct lifecycles:
#
#   1. GENERATION status  — how well the quiz was produced.
#        READY      all requested questions passed validation
#        PARTIAL    >=1 question produced but fewer than requested
#        ERROR      no questions could be produced
#        CANCELLED  deleted/no longer usable
#
#   2. ATTEMPT status    — how a submission was scored.
#        CREATED    quiz handed out, not started
#        STARTED    timer began (started_at set)
#        SUBMITTED  scored (COMPLETED all answered / PARTIAL missing)
#
# Both are surfaced structurally so the API can render them.
# ==========================================================

from dataclasses import dataclass, field, asdict
from enum import Enum

# Option letters are fixed to exactly four options (A, B, C, D).
OPTION_LETTERS = ("A", "B", "C", "D")

REQUIRED_OPTION_COUNT = 4


class GenerationStatus(str, Enum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class AttemptStatus(str, Enum):
    CREATED = "CREATED"
    STARTED = "STARTED"
    SUBMITTED = "SUBMITTED"


@dataclass
class Question:
    """A single authoritative MCQ item."""

    id: str
    prompt: str
    options: list                      # exactly 4 strings, index 0..3
    correct_index: int                 # authoritative index into options
    explanation: str
    evidence: str                      # verbatim snippet from the corpus
    difficulty: str = "medium"
    page: int = None                   # source page (0-based metadata)
    source: str = "document"           # basename of the source file
    rationale: str = ""                # optional generation note

    @property
    def correct_letter(self):
        return OPTION_LETTERS[self.correct_index]

    def public_dict(self):
        """API-safe payload: never reveals the correct answer."""
        return {
            "id": self.id,
            "prompt": self.prompt,
            "options": list(self.options),
            "difficulty": self.difficulty,
            "page": self.page,
            "source": self.source,
        }

    def graded_dict(self):
        """Reveal the authoritative answer after submission/scoring."""
        return {
            **self.public_dict(),
            "correct_index": self.correct_index,
            "correct_letter": self.correct_letter,
            "correct_answer": self.options[self.correct_index],
            "explanation": self.explanation,
            "evidence": self.evidence,
        }


    def to_dict(self):
        """Full authoritative record (includes correct_index) for disk."""
        return {
            "id": self.id,
            "prompt": self.prompt,
            "options": list(self.options),
            "correct_index": self.correct_index,
            "explanation": self.explanation,
            "evidence": self.evidence,
            "difficulty": self.difficulty,
            "page": self.page,
            "source": self.source,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data["id"],
            prompt=data["prompt"],
            options=list(data["options"]),
            correct_index=int(data["correct_index"]),
            explanation=data.get("explanation", ""),
            evidence=data.get("evidence", ""),
            difficulty=data.get("difficulty", "medium"),
            page=data.get("page"),
            source=data.get("source", "document"),
            rationale=data.get("rationale", ""),
        )


@dataclass
class Quiz:
    """Quiz definition (questions + metadata). Authoritative data."""

    id: str
    library_id: str
    subject: str
    questions: list                    # list of Question
    question_count_requested: int
    difficulty: str = "mixed"
    time_limit_seconds: int = 0
    title: str = ""
    created_at: float = 0.0
    generation_status: str = GenerationStatus.READY.value
    partial_reason: str = ""
    version: int = 1

    def public_dict(self, reveal_answers=False):
        """Serialize for the client.

        `reveal_answers` is only used by the server when reporting
        an already-graded result; normal quiz delivery never passes
        correct answers to the client before submission.
        """
        questions = [
            q.graded_dict() if reveal_answers else q.public_dict()
            for q in self.questions
        ]
        return {
            "id": self.id,
            "library_id": self.library_id,
            "subject": self.subject,
            "title": self.title,
            "difficulty": self.difficulty,
            "question_count": len(self.questions),
            "question_count_requested": self.question_count_requested,
            "time_limit_seconds": self.time_limit_seconds,
            "created_at": self.created_at,
            "status": self.generation_status,
            "partial_reason": self.partial_reason,
            "questions": questions,
        }

    def to_dict(self):
        """Full authoritative record for disk (includes correct answers)."""
        return {
            "id": self.id,
            "library_id": self.library_id,
            "subject": self.subject,
            "questions": [q.to_dict() for q in self.questions],
            "question_count_requested": self.question_count_requested,
            "difficulty": self.difficulty,
            "time_limit_seconds": self.time_limit_seconds,
            "title": self.title,
            "created_at": self.created_at,
            "generation_status": self.generation_status,
            "partial_reason": self.partial_reason,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data["id"],
            library_id=data["library_id"],
            subject=data["subject"],
            questions=[
                Question.from_dict(q) for q in data.get("questions", [])
            ],
            question_count_requested=data.get(
                "question_count_requested",
                len(data.get("questions", [])),
            ),
            difficulty=data.get("difficulty", "mixed"),
            time_limit_seconds=data.get("time_limit_seconds", 0),
            title=data.get("title", ""),
            created_at=data.get("created_at", 0.0),
            generation_status=data.get(
                "generation_status",
                GenerationStatus.READY.value,
            ),
            partial_reason=data.get("partial_reason", ""),
            version=data.get("version", 1),
        )


@dataclass
class Attempt:
    """A single quiz session: delivery + submitted answers + score."""

    id: str
    quiz_id: str
    status: str = AttemptStatus.CREATED.value
    created_at: float = 0.0
    started_at: float = None
    submitted_at: float = None
    answers: dict = field(default_factory=dict)   # question_id -> option letter
    timed_out: bool = False
    # Scoring is authoritative: recomputed server-side on submit.
    score: int = 0
    total: int = 0
    correct: list = field(default_factory=list)   # question id -> bool
    result_status: str = ""                       # COMPLETED | PARTIAL
    partial_reason: str = ""

    def dict(self):
        return asdict(self)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data["id"],
            quiz_id=data["quiz_id"],
            status=data.get("status", AttemptStatus.CREATED.value),
            created_at=data.get("created_at", 0.0),
            started_at=data.get("started_at"),
            submitted_at=data.get("submitted_at"),
            answers=data.get("answers", {}),
            timed_out=data.get("timed_out", False),
            score=data.get("score", 0),
            total=data.get("total", 0),
            correct=data.get("correct", []),
            result_status=data.get("result_status", ""),
            partial_reason=data.get("partial_reason", ""),
        )
