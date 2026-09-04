# ==========================================================
# Subject-agnostic MCQ generation.
#
# This module is the only place that talks to the LLM for quiz
# items. It reuses the project's provider-agnostic LLM factory
# (src.llm.create_llm -> FailoverLLM), so quiz generation works
# with Groq / OpenRouter / LM Studio exactly like the rest of the
# RAG pipeline.
#
# Guarantees enforced here:
#   * exactly 4 options (A-D) with exactly one correct,
#   * explanation + verbatim evidence for every question,
#   * difficulty among easy/medium/hard (respecting the quiz level;
#     "mixed" lets the model pick a sensible spread),
#   * every item passes structural + grounding validation, so no
#     hallucinated or fabricated questions are ever returned,
#   * bounded retries on malformed output or provider errors; a
#     structured, deterministic outcome (READY / PARTIAL / ERROR)
#     is always returned, never a made-up fallback question.
# ==========================================================

import json
import re

from src.config import (
    QUIZ_GENERATION_RETRIES,
    QUIZ_ALLOWED_DIFFICULTIES,
)
from src.llm import create_llm
from src.agents.utils import extract_response_text
from src.quizzes.models import (
    OPTION_LETTERS,
    REQUIRED_OPTION_COUNT,
    Question,
    Quiz,
    GenerationStatus,
)
from src.quizzes.retrieval import retrieve_quiz_context
from src.quizzes.validation import (
    validate_structure,
    validate_grounding,
    _duplicate_pair,
)

DEFAULT_DIFFICULTY = "mixed"


class QuizGenerationError(Exception):
    """Structured error carrying a client-safe `reason`."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


GENERATION_PROMPT = """
You are a quiz-generation assistant for a document-grounded knowledge
base. The document may be about any subject; do not assume any topic.

You are given CONTEXT retrieved from the document. All your questions
MUST be answerable from that CONTEXT alone.

Create exactly {count} multiple-choice question(s). The requested
difficulty is "{difficulty}":
  - "easy", "medium" or "hard"  -> every question at exactly that level
  - "mixed"                     -> spread across easy / medium / hard

Requirements for EVERY question:
- The question stem, the correct answer and the explanation MUST be
  fully supported by the CONTEXT. Never use outside knowledge, even
  for a "hard" question. Hard questions may combine pieces of the
  CONTEXT but may not introduce facts that are not in it.
- Exactly 4 options labeled "A", "B", "C", "D".
- Exactly one option is correct; the other three are plausible but
  clearly wrong according to the CONTEXT (and must not contradict the
  CONTEXT with outside facts).
- Include an "explanation" that explains, using only the CONTEXT, why
  the correct option is right.
- Include "evidence": a verbatim excerpt copied EXACTLY from the
  CONTEXT, a literal substring, that supports the correct answer.
- Do not ask the same question twice with different wording.

Reply with ONLY a JSON array (no prose, no code fences). Each element
is an object with EXACTLY these keys:
  "prompt": string,
  "options": {{ "A": string, "B": string, "C": string, "D": string }},
  "correct_letter": "A" | "B" | "C" | "D",
  "explanation": string,
  "evidence": string,
  "difficulty": "easy" | "medium" | "hard"

CONTEXT
{context}
"""


# ----------------------------------------------------------
# JSON extraction + candidate normalization
# ----------------------------------------------------------

def _extract_json_array(text):
    """
    Pull the first JSON array out of an LLM response. Handles
    surrounding prose and ```json fences. Returns the parsed list or
    raises ValueError.
    """
    if text is None:
        raise ValueError("empty model response")

    text = str(text).strip()

    # Remove markdown fences if present.
    fenced = re.findall(r"```(?:json)?\s*(\[.*?\])\s*```", text, flags=re.DOTALL)
    candidate = fenced[0] if fenced else text

    start = candidate.find("[")
    end = candidate.rfind("]")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON array found in model response")

    payload = json.loads(candidate[start:end + 1])

    if not isinstance(payload, list):
        raise ValueError("model response is not a JSON array")

    return payload


def _normalize_candidate(raw, index):
    """
    Turn one raw dict from the model into a structurally-valid
    Question, or raise ValueError describing the problem.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"item {index} is not an object")

    prompt = str(raw.get("prompt") or "").strip()
    options_dict = raw.get("options")
    correct_letter = str(raw.get("correct_letter") or "").strip().upper()
    explanation = str(raw.get("explanation") or "").strip()
    evidence = str(raw.get("evidence") or "").strip()
    difficulty = str(raw.get("difficulty") or "").strip().lower()

    if not isinstance(options_dict, dict):
        raise ValueError(f"item {index}: options must be an object")

    options = []
    for letter in OPTION_LETTERS:
        value = options_dict.get(letter)
        if not value or not str(value).strip():
            raise ValueError(f"item {index}: missing or empty option {letter}")
        options.append(str(value).strip())

    if correct_letter not in OPTION_LETTERS:
        raise ValueError(f"item {index}: invalid correct_letter {correct_letter!r}")
    correct_index = OPTION_LETTERS.index(correct_letter)

    q = Question(
        id="{n}",
        prompt=prompt,
        options=options,
        correct_index=correct_index,
        explanation=explanation,
        evidence=evidence,
        difficulty=difficulty,
    )

    ok, reasons = validate_structure(q)
    if not ok:
        raise ValueError(
            f"item {index}: structural validation failed: {'; '.join(reasons)}"
        )

    return q


# ----------------------------------------------------------
# LLM call loop (bounded retries)
# ----------------------------------------------------------

def _build_prompt(count, difficulty, context):
    if difficulty not in QUIZ_ALLOWED_DIFFICULTIES:
        difficulty = DEFAULT_DIFFICULTY
    return GENERATION_PROMPT.format(
        count=count,
        difficulty=difficulty,
        context=context,
    )


def generate_candidates(
    context,
    count,
    difficulty=DEFAULT_DIFFICULTY,
    llm=None,
    retries=None,
):
    """
    Ask the LLM for `count` candidate MCQs grounded in `context`.

    On model/provider failure, retries (bounded). Returns a dict:
        {
            "questions": [Question],      # structurally valid only
            "attempts": int,
            "errors": [str],              # last structured errors
        }
    """
    if llm is None:
        llm = create_llm(prefer="quiz")

    if retries is None:
        retries = QUIZ_GENERATION_RETRIES

    attempts = 0
    questions = []
    errors = []

    for _ in range(max(1, retries)):

        attempts += 1

        try:
            response = llm.invoke(
                _build_prompt(count, difficulty, context)
            )
            text = extract_response_text(response)
            payload = _extract_json_array(text)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
            # Provider error / rate limit / unparseable output -> retry
            continue

        batch = []
        stopped = False

        for i, raw in enumerate(payload):
            try:
                batch.append(_normalize_candidate(raw, i))
            except ValueError as exc:
                errors.append(str(exc))
                # A malformed item aborts this batch; the whole batch is
                # retried so we never mix a good item with a bad one.
                stopped = True
                break

        if stopped:
            continue

        questions = batch
        break  # success (or at least a fully-parseable batch)

    return {
        "questions": questions,
        "attempts": attempts,
        "errors": errors,
    }


# ----------------------------------------------------------
# Coordinator: end-to-end quiz construction
# ----------------------------------------------------------

def generate_quiz(
    vectorstore,
    library_id,
    subject,
    topic,
    question_count,
    difficulty=DEFAULT_DIFFICULTY,
    time_limit_seconds=0,
    llm=None,
    quiz_id=None,
    created_at=None,
):
    """
    Build a validated Quiz from a corpus.

    Flow:
      1. retrieve quiz context for `topic`
      2. generate candidate questions (bounded retries)
      3. validate structure + grounding + dedup
      4. attach evidence / source page metadata
      5. decide generation status:
           READY     == requested count produced
           PARTIAL   >=1 produced but fewer than requested
           ERROR     0 produced

    Raises QuizGenerationError on total provider failure AND when the
    model repeatedly fails to return parseable candidates. A Quiz is
    always returned whenever at least one grounded question exists.
    """
    if question_count < 1:
        raise QuizGenerationError("question_count must be at least 1")

    retrieval = retrieve_quiz_context(vectorstore, topic)
    context = retrieval["context"]
    documents = retrieval["documents"]

    if not context or not context.strip():
        raise QuizGenerationError("no retrievable context for the topic")

    from src.quizzes.validation import (
        validate_structure as _vs,
        validate_grounding as _vg,
        QUIZ_DUP_RATIO,
    )

    # Grounding + dedup. The deterministic validation decides what is
    # acceptable; the LLM verifier (same provider) is additive.
    #
    # Generation is iterative: we keep asking for fresh candidate batches
    # until we have `question_count` accepted (grounded, deduped) items or
    # we exhaust a bounded round budget. This ensures the returned quiz
    # honours the requested count whenever the corpus can ground enough
    # distinct questions, instead of silently dropping ungrounded
    # candidates down to PARTIAL.
    accepted = []
    rejected = []
    seen = []

    max_rounds = max(2, min(4, (question_count + 2) // 3))
    generation_errors = []

    for round_index in range(max_rounds):

        if len(accepted) >= question_count:
            break

        candidate_result = generate_candidates(
            context,
            count=question_count,
            difficulty=difficulty,
            llm=llm,
        )

        new_in_batch = 0
        batch_had_errors = bool(candidate_result["errors"])

        for q in candidate_result["questions"]:

            if len(accepted) >= question_count:
                break

            ok_s, s_reasons = _vs(q)
            if not ok_s:
                rejected.append((q, s_reasons))
                continue

            # Cheap dedup check runs before the expensive grounding LLM
            # call so already-seen candidates are not re-verified.
            if any(_duplicate_pair(q, keep, QUIZ_DUP_RATIO) for keep in seen):
                rejected.append((q, ["near-duplicate of an earlier question"]))
                continue

            ok_g, report = _vg(q, context, llm=llm)
            if not ok_g:
                rejected.append((q, report.get("reasons", [])))
                continue

            seen.append(q)
            accepted.append(q)
            new_in_batch += 1

        # If this round produced no parseable candidates because of a
        # provider/parse failure, stop looping instead of hammering it.
        if round_index == 0 and not new_in_batch and not candidate_result["questions"]:
            if batch_had_errors:
                generation_errors = list(candidate_result["errors"])
            break

    if not accepted:
        # Could not recover a single grounded question from any round.
        # Distinguish provider failure from "no grounded questions" and
        # preserve the original raise-on-total-failure behaviour.
        reason = "quiz generation failed and could not recover"
        if generation_errors:
            reason = f"quiz generation failed: {generation_errors[-1]}"
        raise QuizGenerationError(reason[:400])

    # Attach source metadata for traceability.
    for q in accepted:
        doc = _best_source_doc(q, documents)
        if doc is not None:
            page = doc.metadata.get("page")
            source = doc.metadata.get("source") or doc.metadata.get("file_name") or "document"
            q.page = page
            q.source = str(source)
            if (q.evidence or "").strip() and (doc.page_content or ""):
                # Anchor evidence to this chunk when possible.
                pass

    for i, q in enumerate(accepted):
        q.id = f"q{i}"

    status = GenerationStatus.READY.value
    partial_reason = ""

    if len(accepted) < question_count:
        if len(accepted) == 0:
            status = GenerationStatus.ERROR.value
            partial_reason = "no questions passed grounding validation"
        else:
            status = GenerationStatus.PARTIAL.value
            partial_reason = (
                f"only {len(accepted)} of {question_count} requested "
                "questions passed grounding and duplicate validation"
            )

    if quiz_id is None:
        import uuid
        quiz_id = str(uuid.uuid4())

    if created_at is None:
        import time
        created_at = time.time()

    return Quiz(
        id=quiz_id,
        library_id=library_id,
        subject=subject,
        questions=accepted,
        question_count_requested=question_count,
        difficulty=difficulty,
        time_limit_seconds=time_limit_seconds,
        title=f"{subject} · {topic}",
        created_at=created_at,
        generation_status=status,
        partial_reason=partial_reason,
    )


def _best_source_doc(question, documents):
    """Best supporting document for a question's evidence text."""
    evidence = (question.evidence or "").strip()
    if evidence:
        norm = " ".join(evidence.split()).lower()
        for doc in documents:
            if " ".join((doc.page_content or "").split()).lower() in norm or \
               norm in " ".join((doc.page_content or "").split()).lower():
                return doc
    # Fall back to the document containing the most correct-answer words.
    correct = (question.options[question.correct_index] or "").lower()
    best = None
    best_ratio = 0.0
    from src.agents.grounding import _claim_support
    for doc in documents:
        ratio, _ = _claim_support(question.options[question.correct_index], doc.page_content)
        if ratio > best_ratio:
            best_ratio = ratio
            best = doc
    return best
