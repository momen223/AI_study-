# ==========================================================
# Quiz item validation.
#
# Enforces the anti-hallucination guarantee for generated MCQs:
#
#   1. STRUCTURAL  — exactly 4 unique options, one correct, valid
#                    difficulty, all text fields populated.
#   2. GROUNDING   — the question stem, the correct answer and the
#                    explanation are all supported by the retrieved
#                    context (deterministic gate dominates), and the
#                    optional LLM verification finds no outside
#                    knowledge or contradictions.
#   3. DEDUP       — near-duplicate / repeated questions are dropped.
#
# The deterministic checks are deliberate: an item is rejected even
# if the verifying LLM claims it is supported, whenever its wording
# cannot be traced back to the retrieved context (same philosophy as
# the chat grounding agent's deterministic gate).
# ==========================================================

import difflib

from src.config import QUIZ_MIN_SUPPORT, QUIZ_DUP_RATIO
from src.agents.grounding import (
    _content_tokens,
    _claim_support,
)
from src.agents.utils import extract_response_text
from src.quizzes.models import (
    OPTION_LETTERS,
    REQUIRED_OPTION_COUNT,
)


VALIDATE_PROMPT = """
You are a quiz grounding verifier.

The CONTEXT is the only source of truth. The document may be about
any subject; do not assume any topic.

Verify that the QUESTION, the CORRECT ANSWER, and the EXPLANATION
are ALL fully supported by the CONTEXT, with no outside knowledge,
no invented facts or examples, no contradictions, and no mixing of
two different concepts. The incorrect options may be plausible but
must not state a fact that the CONTEXT contradicts.

The question wording is allowed to differ from the CONTEXT as long
as the underlying fact is present.

Reply with exactly one line: PASS or FAIL.

QUESTION
{question}

CORRECT ANSWER
{correct}

EXPLANATION
{explanation}

CONTEXT
{context}

VERDICT
"""


# ----------------------------------------------------------
# STRUCTURAL validation
# ----------------------------------------------------------

def validate_structure(question):
    """
    Return (ok: bool, reasons: list[str]).

    Checks that a candidate has exactly 4 distinct, non-empty options,
    a single valid correct index, a non-empty prompt / explanation /
    evidence, and a valid difficulty. This runs at parse time so
    malformed model output is rejected and re-prompted (bounded).
    """
    reasons = []

    prompt = (question.prompt or "").strip()
    if not prompt:
        reasons.append("empty question prompt")

    options = question.options
    if not isinstance(options, list) or len(options) != REQUIRED_OPTION_COUNT:
        reasons.append(
            f"expected {REQUIRED_OPTION_COUNT} options, got {len(options)}"
        )
    else:
        cleaned = [str(o or "").strip() for o in options]
        if any(not o for o in cleaned):
            reasons.append("empty option text")
        if len(set(cleaned)) != REQUIRED_OPTION_COUNT:
            reasons.append("options are not all distinct")

    ci = question.correct_index
    if not (isinstance(ci, int) and 0 <= ci < REQUIRED_OPTION_COUNT):
        reasons.append("invalid correct index")
    elif options and len(options) == REQUIRED_OPTION_COUNT:
        cleaned = [str(o or "").strip() for o in options]
        if cleaned[ci] and any(o == cleaned[ci] for o in cleaned[:ci] + cleaned[ci + 1:]):
            reasons.append("correct answer duplicated among options")

    if not (question.explanation or "").strip():
        reasons.append("empty explanation")

    if not (question.evidence or "").strip():
        reasons.append("empty evidence")

    if question.difficulty not in ("easy", "medium", "hard"):
        reasons.append(f"invalid difficulty: {question.difficulty}")

    return not reasons, reasons


# ----------------------------------------------------------
# GROUNDING validation (deterministic gate + optional LLM)
# ----------------------------------------------------------

def _support_ratio(text, context):
    """Fraction of `text`'s content words found in `context`."""
    ratio, _ = _claim_support(text, context)
    return ratio


def grounded(question, context, llm=None):
    """
    Decide whether a question's stem, correct answer and explanation
    are supported by the retrieved `context`.

    Deterministic gate (always runs):
      - evidence must be a verbatim substring of the context (so the
        "proof" cannot be fabricated),
      - stem / correct answer / explanation content-word support must
        meet QUIZ_MIN_SUPPORT.

    Optional LLM layer (runs when an llm is supplied): flags outside
    knowledge / contradictions. Failures here are additive: any reason
    fails the item.

    Returns (ok: bool, report: dict).
    """
    reason_list = []

    context_norm = " ".join(str(context or "").split())
    evidence = " ".join(str(question.evidence or "").split())

    # Verbatim evidence requirement: the cited proof must literally
    # appear in the retrieved context.
    if not evidence or evidence not in context_norm:
        reason_list.append("evidence not a verbatim excerpt of the context")

    stem_ratio = _support_ratio(question.prompt, context)
    correct_ratio = _support_ratio(
        question.options[question.correct_index],
        context,
    )
    explanation_ratio = _support_ratio(question.explanation, context)

    if stem_ratio < QUIZ_MIN_SUPPORT:
        reason_list.append(
            f"question stem unsupported by context (support {stem_ratio:.2f})"
        )
    if correct_ratio < QUIZ_MIN_SUPPORT:
        reason_list.append(
            f"correct answer unsupported by context (support {correct_ratio:.2f})"
        )
    if explanation_ratio < QUIZ_MIN_SUPPORT:
        reason_list.append(
            f"explanation unsupported by context (support {explanation_ratio:.2f})"
        )

    llm_error = False
    if llm is not None:
        try:
            response = llm.invoke(
                VALIDATE_PROMPT.format(
                    question=question.prompt,
                    correct=question.options[question.correct_index],
                    explanation=question.explanation,
                    context=context,
                )
            )
            verdict = extract_response_text(response).strip().lower()
        except Exception:  # noqa: BLE001
            verdict = ""
            llm_error = True
        if verdict and verdict.startswith("fail"):
            reason_list.append(
                "verifier: content not supported by the context"
            )

    report = {
        "stem_ratio": round(stem_ratio, 3),
        "correct_ratio": round(correct_ratio, 3),
        "explanation_ratio": round(explanation_ratio, 3),
        "evidence_verbatim": bool(evidence) and evidence in context_norm,
        "llm_error": llm_error,
        "reasons": reason_list,
    }

    return not reason_list, report


def validate_grounding(question, context, llm=None):
    """Convenience: returns (ok: bool, report: dict)."""
    return grounded(question, context, llm=llm)


# ----------------------------------------------------------
# DUPLICATE prevention
# ----------------------------------------------------------

def _sim(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def _duplicate_pair(q1, q2, ratio):
    """Two questions are near-duplicates if their stems or option sets
    are very similar."""
    stem = _sim(
        (q1.prompt or "").strip().lower(),
        (q2.prompt or "").strip().lower(),
    )
    opt = _sim(
        "|".join(str(o).strip().lower() for o in q1.options),
        "|".join(str(o).strip().lower() for o in q2.options),
    )
    return stem >= ratio or opt >= ratio


def deduplicate(questions, ratio=None):
    """
    Drop near-duplicate / repeated questions, keeping the first
    occurrence. Returns (unique_list, dropped_count).
    """
    if ratio is None:
        ratio = QUIZ_DUP_RATIO

    unique = []
    dropped = 0

    for q in questions:
        if any(_duplicate_pair(q, keep, ratio) for keep in unique):
            dropped += 1
            continue
        unique.append(q)

    return unique, dropped


def validate_quiz_questions(
    questions,
    context,
    llm=None,
    dedup_ratio=None,
):
    """
    Run the full pipeline over candidate `questions`:

      1. structural validation
      2. grounding validation against `context`
      3. near-duplicate removal

    Returns (accepted: list, rejected: list of (question, reasons)).
    """
    accepted = []
    rejected = []

    seen = []

    for q in questions:

        ok_struct, struct_reasons = validate_structure(q)
        if not ok_struct:
            rejected.append((q, struct_reasons))
            continue

        ok_ground, report = validate_grounding(q, context, llm=llm)
        if not ok_ground:
            rejected.append((q, report.get("reasons", [])))
            continue

        if any(_duplicate_pair(q, keep, dedup_ratio or QUIZ_DUP_RATIO) for keep in seen):
            rejected.append((q, ["near-duplicate of an earlier question"]))
            continue

        seen.append(q)
        accepted.append(q)

    return accepted, rejected
