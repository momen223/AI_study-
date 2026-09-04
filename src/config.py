# ==========================================================
# Global configuration for the RAG system.
#
# Chroma distance semantics:
#   LOWER = MORE SIMILAR
#   HIGHER = LESS SIMILAR
#
# All shared parameters live here so they are never
# duplicated across the project.
# ==========================================================

RETRIEVAL_DISTANCE_THRESHOLD = 0.50

STRONG_RELEVANCE_THRESHOLD = 0.35

RELEVANCE_CHECK_K = 5

# Minimum number of strong chunks (score <= STRONG_RELEVANCE_THRESHOLD)
# required to consider the query relevant.
MIN_STRONG_CHUNKS = 1

# Minimum number of moderately-relevant chunks
# (score <= RETRIEVAL_DISTANCE_THRESHOLD) required to consider the
# query relevant when there is no strong single match.
MIN_RELEVANT_CHUNKS = 3

# Tolerance band above STRONG_RELEVANCE_THRESHOLD used by the
# evidence-coverage fallback: a query with no strong single match is
# still relevant only if its best score is within this band of strong
# AND at least MIN_RELEVANT_CHUNKS chunks corroborate it.
RELEVANCE_BAND = 0.10

RETRIEVER_K = 5

FETCH_K = 10

# MMR diversity/relevance trade-off. Empirically tuned so that
# a definition chunk and its example table are NOT both treated
# as near-duplicates (which caused the definition to be dropped
# as a false negative). Higher = more relevance-focused.
MMR_LAMBDA = 0.95

# Chroma persistence.
# Overridable via environment variables so no code edits are needed to point
# the system at a different store (e.g. a per-subject store). The defaults
# below match the primary example store built by scripts/build_vectorstore.py.
import os

PERSIST_DIRECTORY = os.environ.get("PERSIST_DIRECTORY", "./chroma_db")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "data_warehousing")

# ==========================================================
# Quiz (MCQ) generation feature.
#
# These parameters govern the backend-only multi-select quiz
# generator. All values are config-driven so no logic is
# hardcoded. They are independent of the chat thresholds above.
# ==========================================================

# Number of questions requested by default when a quiz is created
# without an explicit count.
QUIZ_DEFAULT_QUESTION_COUNT = 5

# Hard upper bound. Requests above this are rejected by the API.
QUIZ_MAX_QUESTION_COUNT = 20

# The quiz retriever pulls more context than a normal chat query
# because every question (stem, correct option, explanation) must
# be grounded against the retrieved material. MMR is reused; only
# the k/fetch_k are increased for quiz purposes.
QUIZ_RETRIEVAL_K = 12
QUIZ_FETCH_K = 20

# Bounded retries when the LLM returns malformed / unparseable MCQ
# JSON or raises a transient provider error. Each retry re-asks the
# model with the same context; failures with structured reasons are
# surfaced, never silently replaced with a fabricated question.
QUIZ_GENERATION_RETRIES = 3

# Deterministic grounding gate for quiz items. A generated option or
# explanation is rejected when fewer than this fraction of its content
# words appear in its supporting chunk. This mirrors the chat
# grounding philosophy: the deterministic gate dominates the LLM.
QUIZ_MIN_SUPPORT = 0.30

# Near-duplicate drop threshold (0..1). Two candidate questions whose
# stem text (or option sets) match at least this strongly are treated
# as duplicates; only the first is kept.
QUIZ_DUP_RATIO = 0.90

# Allowed difficulty levels for a quiz. "mixed" lets the generator pick.
QUIZ_ALLOWED_DIFFICULTIES = ("easy", "medium", "hard", "mixed")

# Default time limit (seconds) applied when a quiz is created without
# one. 0 means no time limit (the timer still records started_at /
# submitted_at deltas).
QUIZ_DEFAULT_TIME_LIMIT_SECONDS = 0

# Where quiz definitions + results are persisted (JSON index), mirroring
# the uploads/index.json pattern so quizzes survive process restarts.
QUIZ_STORE_DIR = "./quiz_store"