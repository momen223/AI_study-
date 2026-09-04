import re

from src.llm import create_llm
from src.agents.utils import (
    extract_response_text,
    build_context,
)
from src.agents.relevance import STOPWORDS
from src.agents.answer_generation import UNKNOWN_ANSWER


# ==========================================================
# Grounding / Verification Agent
#
# Checks the generated answer before it is returned:
#
#   - Is every important claim supported?
#   - Did the answer introduce outside knowledge?
#   - Did it invent examples?
#   - Did it answer the actual question?
#   - Did it contradict the context?
#   - Did it confuse two concepts?
#   - Did it answer a follow-up using the wrong reference?
#
# Two verification layers:
#
#   1. DETERMINISTIC (always runs, no LLM):
#        - claim support ratio (answer tokens present in context)
#        - unattested numbers (hallucinated statistics)
#        - question/answer topical overlap
#
#   2. LLM-BASED (runs when llm available):
#        - contradiction / concept confusion / wrong reference
#        - invented examples / outside knowledge
#
# Output:
#   PASS or FAIL with reasons.
#   When the answer is the UNKNOWN fallback there is nothing to
#   verify -> SKIPPED/PASS.
# ==========================================================

MIN_SUPPORT_RATIO = 0.45

MIN_QUESTION_OVERLAP = 0.40

VERIFY_PROMPT = """
You are a grounding and verification assistant.

Your ONLY job is to verify that the ANSWER is fully supported
by the CONTEXT.

The CONTEXT is the only source of truth. The document may be
about any subject — do not assume any topic.

Check the ANSWER for:

- claims that are NOT supported by CONTEXT
- outside knowledge (facts not present in CONTEXT)
- invented examples
- contradictions with CONTEXT
- mixing or confusing two different concepts
- answering a different question than the one asked
- wrong reference resolution in a follow-up conversation

The ANSWER may reformulate the CONTEXT in different words,
use synonyms, restructure, or copy a page reference (e.g.
"Page 15") from the CONTEXT. Those are allowed. Do NOT fail
an answer merely because its wording differs from the CONTEXT.

If EVERY important claim is supported and the answer addresses
the question, respond PASS.

Otherwise respond FAIL.

Your reply must start with exactly one line: PASS or FAIL.
After that line you may list concise reasons.

==========================================================
QUESTION
==========================================================

{question}

==========================================================
ANSWER
==========================================================

{answer}

==========================================================
CONTEXT
==========================================================

{context}

==========================================================
VERDICT
==========================================================
"""


def _tokenize(text):
    """
    Split on whitespace/punctuation AND on camelCase
    boundaries, so "ProductKey" becomes ["Product", "Key"].
    Prevents code identifiers from looking like invented
    entities and keeps the support ratio honest.
    """

    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)

    return re.findall(r"[a-zA-Z0-9]+", text)


def _content_tokens(text):
    """
    Case-folded alphanumeric tokens, stopwords removed.
    """

    words = _tokenize(text.lower())

    return [
        word
        for word in words
        if word not in STOPWORDS
    ]


def _dedupe(items):
    """Preserve order, drop duplicates."""

    seen = set()
    result = []

    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)

    return result


def _claim_support(answer, context):
    """
    Fraction of the answer's content tokens that appear in
    the context. Paraphrase-penalty is acceptable: contest is
    built from doc vocabulary that grounded answers reuse.
    """

    answer_tokens = _content_tokens(answer)

    if not answer_tokens:
        return 1.0, []

    context_lower = context.lower()

    unsupported = _dedupe([
        token
        for token in answer_tokens
        if token not in context_lower
    ])

    supported = len(answer_tokens) - len(unsupported)

    ratio = supported / len(answer_tokens)

    return ratio, unsupported


def _unattested_numbers(answer, context):
    """
    Numbers present in the answer but absent from the context
    (page markers stripped) are hallucinated statistics.

    Page citations that the model copies from the CONTEXT's
    [PAGE n] markers (e.g. "(Page 15)") are NOT statistics.

    List/ordinal enumeration markers are structural formatting,
    not data. The generator often numbers a list ("1. Foo",
    "2) Bar", "1st/2nd") when the retrieved context does not
    contain those literal digits, so they are stripped before
    scanning for real statistics.
    """

    answer_clean = re.sub(
        r"\bpage\s+\d+(?:\.\d+)?\b",
        "",
        answer,
        flags=re.IGNORECASE,
    )

    # Drop list-enumeration markers ("1.", "2)", "3.") and
    # cardinal ordinals ("1st", "2nd", "3rd") -- structural, not data.
    answer_clean = re.sub(
        r"\b\d+(?:st|nd|rd|th)\b",
        "",
        answer_clean,
        flags=re.IGNORECASE,
    )
    answer_clean = re.sub(
        r"\b\d+\s*[.)](?=\s|$)",
        "",
        answer_clean,
    )

    numbers = re.findall(
        r"\b\d+(?:\.\d+)?\b",
        answer_clean,
    )

    if not numbers:
        return []

    numbers = _dedupe(numbers)

    context_no_pages = re.sub(
        r"\[PAGE \d+\]",
        "",
        context,
    )

    context_numbers = set(
        re.findall(
            r"\b\d+(?:\.\d+)?\b",
            context_no_pages,
        )
    )

    return [
        number
        for number in numbers
        if number not in context_numbers
    ]


def _unattested_proper_nouns(answer, context):
    """
    Capitalized words in the answer that do not appear in the
    context. Invented names/entities (e.g. "Bill Inmon") are
    the classic hallucination and are caught here directly,
    without depending on the aggregate support ratio.

    Normal sentence/table styling (a safely capitalized common
    word such as "Explicit") is NOT an entity, so only tokens
    that look like real names are flagged:

      - capitalized tokens that appear in an adjacent run of
        two or more capitalized words ("Bill Inmon"), or
      - the same token capitalized more than once
        (a repeated invented name).

    An isolated capitalized word ("Explicit", "Types") is
    treated as ordinary capitalization and ignored.
    """

    context_lower = context.lower()

    tokens = _tokenize(answer)

    capital_runs = set()

    for i in range(len(tokens) - 1):
        a, b = tokens[i], tokens[i + 1]
        if (
            a[:1].isupper()
            and b[:1].isupper()
            and a.lower() not in STOPWORDS
            and b.lower() not in STOPWORDS
        ):
            capital_runs.add(a)
            capital_runs.add(b)

    capital_counts = {}

    for token in tokens:
        if token[:1].isupper():
            capital_counts[token] = capital_counts.get(token, 0) + 1

    flagged = []

    for token in _dedupe(tokens):
        if (
            token[:1].isupper()
            and token.lower() not in STOPWORDS
            and token.lower() not in context_lower
            and (
                token in capital_runs
                or capital_counts.get(token, 0) >= 2
            )
        ):
            flagged.append(token)

    return flagged


def _question_overlap(question, answer):
    """
    Fraction of the question's content tokens that appear in
    the answer. Detects off-topic answers.
    """

    question_tokens = _content_tokens(question)

    if len(question_tokens) < 2:
        return 1.0

    answer_lower = answer.lower()

    matched = sum(
        1
        for token in question_tokens
        if token in answer_lower
    )

    return matched / len(question_tokens)


def verify_grounding(
    question,
    answer,
    documents,
    rewritten_question=None,
    llm=None,
):
    """
    Verify the answer against the provided documents.

    Returns a dict:
        {
            "verdict":   "PASS" | "FAIL",
            "status":    "PASS" | "FAIL" | "SKIPPED",
            "reasons":   list of str,
            "checks":    dict of deterministic signals,
            "llm_error": bool,
        }
    """

    if not answer or answer == UNKNOWN_ANSWER:

        return {
            "verdict": "PASS",
            "status": "SKIPPED",
            "reasons": ["unknown answer: nothing to verify"],
            "checks": {},
            "llm_error": False,
        }

    if not documents:

        return {
            "verdict": "FAIL",
            "status": "FAIL",
            "reasons": ["no documents to ground the answer"],
            "checks": {},
            "llm_error": False,
        }

    context = build_context(documents)

    reasons = []

    # ------------------------------------------------
    # Deterministic checks
    # ------------------------------------------------

    support_ratio, unsupported = _claim_support(
        answer,
        context,
    )

    unattested = _unattested_numbers(
        answer,
        context,
    )

    unattested_entities = _unattested_proper_nouns(
        answer,
        context,
    )

    if rewritten_question:
        check_question = rewritten_question
    else:
        check_question = question

    overlap_ratio = _question_overlap(
        check_question,
        answer,
    )

    if support_ratio < MIN_SUPPORT_RATIO:

        reasons.append(
            "unsupported claims: "
            + ", ".join(unsupported[:8])
        )

    if unattested:

        reasons.append(
            "unattested numbers: "
            + ", ".join(unattested[:8])
        )

    if unattested_entities:

        reasons.append(
            "unattested entities: "
            + ", ".join(unattested_entities[:8])
        )

    if (
        bool(_content_tokens(check_question or ""))
        and overlap_ratio < MIN_QUESTION_OVERLAP
    ):

        reasons.append(
            f"answer does not address the question "
            f"(topical overlap {overlap_ratio:.2f})"
        )

    # ------------------------------------------------
    # LLM-based verification
    # ------------------------------------------------

    llm_error = False

    if llm is None:
        llm = create_llm(prefer="grounding")

    try:

        response = llm.invoke(
            VERIFY_PROMPT.format(
                question=check_question,
                answer=answer,
                context=context,
            )
        )

        verification = extract_response_text(response).strip()

    except Exception as exc:  # noqa: BLE001
        verification = ""
        llm_error = True

    if verification.lower().startswith("fail"):

        reasons.append(
            "verifier: " + verification[:200]
        )

    # ------------------------------------------------
    # Combine
    # ------------------------------------------------

    if reasons:

        verdict = "FAIL"
        status = "FAIL"

    else:

        verdict = "PASS"
        status = "PASS"

    return {
        "verdict": verdict,
        "status": status,
        "reasons": reasons,
        "checks": {
            "support_ratio": round(support_ratio, 3),
            "question_overlap_ratio": round(overlap_ratio, 3),
            "unsupported_tokens": unsupported[:8],
            "unattested_numbers": unattested[:8],
            "unattested_entities": unattested_entities[:8],
        },
        "llm_error": llm_error,
    }