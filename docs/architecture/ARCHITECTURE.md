# Architecture

This document explains how the Agentic RAG system is structured and how a
question flows through it. The design goal is **subject-agnosticism**: the same
code and prompts answer questions over any document set, with a hard
anti-hallucination guarantee.

## 1. Pipeline overview

A question is processed by a linear chain of agents with an off-topic branch:

```text
User Question
     │
     ▼
Query Understanding Agent      intent, references, standalone question
     │
     ▼
Query Rewriting Agent          follow-ups → self-contained query
     │
     ▼
Retrieval Agent                MMR retrieval over the selected vector store
     │
     ▼
Relevance / Evidence Agent     is the context on-topic?
     │
     ├── RELEVANT  ──► Answer Generation Agent ─► Grounding Agent ─► Final Answer
     └── NOT_RELEVANT ──► "I don't know based on the provided document."
```

### Agent 1 — Query Understanding
`src/agents/query_understanding.py`
Understands intent *without answering*. Produces a standalone question and
detected references from the raw question + chat history.

### Agent 2 — Query Rewriting
`src/agents/query_rewriting.py`
Converts follow-ups into self-contained search queries (e.g. "What are its
types?" → "What are the types of dimensions?"). Failure-tolerant: on provider
error, the question passes through unchanged.

### Agent 3 — Retrieval
`src/agents/retrieval.py`
Runs maximum-marginal-relevance (MMR) retrieval with `RETRIEVER_K`, `FETCH_K`,
and `MMR_LAMBDA` from `config.py`. Returns documents with page numbers,
similarity scores, and the effective `k`. Subject-agnostic: it only matches
query↔document embeddings.

### Agent 4 — Relevance / Evidence
`src/agents/relevance.py`
Decides whether the retrieved context actually addresses the question. Outputs
`RELEVANT` / `NOT_RELEVANT`, a score, overlap data, and a reason. **This is the
single safety gate**: off-topic questions never reach the generator, preventing
hallucination.

### Agent 5 — Answer Generation
`src/agents/answer_generation.py`
A generic, subject-agnostic prompt. Returns `OK | UNKNOWN | ERROR`:
- `OK` → a grounded answer
- `UNKNOWN` → the exact fallback `"I don't know based on the provided document."`
- `ERROR` → provider failure

### Agent 6 — Grounding / Verification
`src/agents/grounding.py`
Verifies the delivered answer is fully supported by the retrieved documents.
Outputs `PASS | FAIL` with per-claim checks. If an answer fails grounding once,
the generator gets one corrective pass with the grounding reasons; only a second
`PASS` is accepted, otherwise the fallback is returned. An `UNKNOWN` answer is
inherently safe → grounding is skipped/PASS.

### Workflow
`src/agents/workflow.py` chains the agents into `run_rag(question,
chat_history, vectorstore)` and exposes the legacy `ask_question(...)` API
through `src/rag.py`.

## 2. Corrective / recovery behaviors

Two corrective passes reduce flakiness **without weakening the
anti-hallucination guarantee**:

1. **UNKNOWN on RELEVANT context**: if the generator returns `UNKNOWN` while
   retrieval + relevance judged the context `RELEVANT`, one corrective
   generation pass tells the model to scan the whole context before giving up.
   If it still returns `UNKNOWN`, the safe fallback is returned. On
   `NOT_RELEVANT` no retry happens.

2. **Grounding FAIL**: a delivered answer that fails grounding is regenerated
   once with the grounding reasons as feedback; only a second `PASS` is
   accepted, otherwise the answer is dropped for the fallback.

These are **model-quality recoveries**, not subject-specific hardcoding.

## 3. Trace shape

`run_rag` returns a rich trace dict used by the API and UI:

- `intent`, `standalone_question`, `rewrote`
- `retrieval` → `{documents, metadata, pages, scores, k, query}`
- `relevance` → `{verdict, reason, best_score, strong_count, relevant_count}`
- `grounding` → `{verdict, status, reasons}`
- `answer`, `result`, `error`

The API (`api/app.py`) deliberately exposes **only safe structured metadata**
(intent, rewritten question, verdicts, citations, scores). It never leaks raw
chain-of-thought and never returns ungrounded content. Citation `source` fields
are normalized to **filenames only** (`os.path.basename`) so no machine-specific
paths ever appear in the UI or API output.

## 4. LLM provider strategy

- Provider selection, keys, and models are configured in `.env` /
  `src/config.py` (`PRIMARY_LLM_PROVIDER`, `FALLBACK_LLM_PROVIDER`,
  `GROQ_MODEL`, `OPENROUTER_MODEL`, …).
- A `FailoverLLM` layer tries the primary provider, then the fallback.
- Intermediate agents read per-stage routing vars (`ANSWER_LLM_PROVIDER`,
  `GROUNDING_LLM_PROVIDER`, …) so specific stages can be pinned to stronger
  models.
- If every provider is unavailable, agents return a structured "providers
  unavailable" result instead of guessing.

## 5. Configurable parameters

All tuning values live in `src/config.py` and are env-overridable
(`PERSIST_DIRECTORY`, `COLLECTION_NAME`). They must not be duplicated elsewhere:

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `RETRIEVAL_DISTANCE_THRESHOLD` | 0.50 | distance below which a chunk is a candidate (lower = more similar) |
| `STRONG_RELEVANCE_THRESHOLD` | 0.35 | distance for a strong-relevance hit |
| `MIN_STRONG_CHUNKS` | 1 | strong hits needed |
| `MIN_RELEVANT_CHUNKS` | 3 | relevant hits needed |
| `RELEVANCE_BAND` | 0.10 | band around the best score |
| `RELEVANCE_CHECK_K` | 5 | chunks sent to the relevance agent |
| `RETRIEVER_K` | 5 | MMR result count |
| `FETCH_K` | 10 | MMR candidate pool |
| `MMR_LAMBDA` | 0.95 | relevance vs diversity balance |

> Note: `MMR_LAMBDA` is raised from the spec-default 0.7 to 0.95 so MMR stays
> relevance-focused, which fixed a retrieval false-negative on a brief canonical
> definition chunk without any prompt change.

## 6. Design rules

1. **Do not** solve test failures by hardcoding expected answers into prompts.
2. The RAG system must not know what subject a document is about — it sees only
   the user question + retrieved content.
3. All parameters come from `src/config.py`.
4. Prompts are subject-agnostic. The test suite greps `src/` for
   subject-specific terms and requires zero hits in prompt text.

## 7. Multi-library storage

- Primary corpus → `./chroma_db` (collection `data_warehousing`)
- Subject corpora → `./chroma_db_subjects/*` (`databases`, `networks`,
  `machine_learning`)
- Uploaded documents → `uploads/files/*.pdf` + `uploads/stores/*`

`api/libraries.py` enumerates the physical store directories and reports each
library's availability, so the UI can list and select them dynamically.

## 8. MCQ quiz generation

A second, independent feature lives under `src/quizzes/` and is exposed through
the `api/quizzes.py` Flask blueprint. It is **subject-agnostic** and **does not
touch the chat pipeline**: it reuses the same retrieval, grounding, and LLM
components with dedicated `QUIZ_*` settings.

### Modules

| Module | Responsibility |
|--------|----------------|
| `src/quizzes/models.py` | `Question`, `Quiz`, `Attempt` dataclasses + `GenerationStatus` / `AttemptStatus` enums. `Question.correct_letter` is a read-only property. |
| `src/quizzes/retrieval.py` | MMR retrieval with `QUIZ_RETRIEVAL_K` / `QUIZ_FETCH_K` over the selected library store. |
| `src/quizzes/validation.py` | Structural validation (exactly 4 options A–D, exactly 1 correct, non-empty evidence, valid difficulty), deterministic grounding gate, and near-duplicate removal. |
| `src/quizzes/generation.py` | `generate_quiz()` and `generate_candidates()` — converts a prompt payload into validated `Question`s with bounded retries. |
| `src/quizzes/lifecycle.py` | `QuizStore` (JSON persistence) and attempt lifecycle (created / started / submitted) with server-side scoring. |
| `api/quizzes.py` | Flask blueprint wiring the above to REST endpoints. |

### Generation flow

```text
POST /api/quizzes  { library, question_count, difficulty, ... }
     │
     ▼
Retrieve context  (MMR, QUIZ_RETRIEVAL_K / QUIZ_FETCH_K)
     │
     ▼
Generate candidates  (LLM, subject-agnostic MCQ prompt)
     │
     ▼
Validate structure  (4 options, 1 correct letter, evidence present)
     │
     ▼
Validate grounding  (deterministic gate over retrieved context:
                     stem + correct answer + explanation all supported)
     │
     ▼
Deduplicate  (near-duplicate removal)
     │
     ▼
Persist quiz  (correct answers stored server-side, QuizStore JSON)
```

Questions that fail structural or grounding validation are rejected (not
retried until a meaningless loop); generation has a bounded retry
(`QUIZ_GENERATION_RETRIES`) that only retries on transient provider failures.
The result status is `READY` (all requested questions produced) or `PARTIAL`
with a structured `reason` — never a fabricated question.

### Grounding guarantee

The deterministic gate reuses `src/agents/grounding.py`'s
`_content_tokens` / `_claim_support`. A candidate is kept only if:

- the **stem** is supported by the context (`ratio >= QUIZ_MIN_SUPPORT`),
- the **correct answer** is supported (no unsupported facts),
- the **explanation** is supported,
- the **evidence** field quotes the retrieved context (verbatim check).

Difficulty (`easy` / `medium` / `hard` / `mixed`) is applied to the LLM prompt
only; it can never introduce facts the grounding gate would reject.

### Attempt lifecycle & security

- `create_attempt` → `CREATED`; `start_attempt` → `STARTED` (records
  `started_at`); `submit` → `COMPLETED` (or `PARTIAL` if unanswered questions
  remain, with a structured `partial_reason`).
- Correct answers are stored server-side and **never returned before
  submission**. Submissions are the only untrusted input; scoring is recomputed
  authoritatively on the server.
- Timer: `time_limit_seconds` (0 = none). If `submitted_at` exceeds
  `started_at + time_limit_seconds`, the attempt is marked `timed_out` and only
  answers within the window count.
- Errors are surfaced as sanitized, structured reasons only (no stack traces).

### Quiz configuration

All `QUIZ_*` constants live in `src/config.py` (env-overridable):
`QUIZ_DEFAULT_QUESTION_COUNT` (5), `QUIZ_MAX_QUESTION_COUNT` (20),
`QUIZ_RETRIEVAL_K` (12), `QUIZ_FETCH_K` (20), `QUIZ_GENERATION_RETRIES` (3),
`QUIZ_MIN_SUPPORT` (0.30), `QUIZ_DUP_RATIO` (0.90),
`QUIZ_ALLOWED_DIFFICULTIES` (easy/medium/hard/mixed),
`QUIZ_DEFAULT_TIME_LIMIT_SECONDS` (0), `QUIZ_STORE_DIR` (`./quiz_store`).
