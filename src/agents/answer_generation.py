from src.llm import create_llm, ProviderUnavailableError
from src.agents.utils import (
    extract_response_text,
    build_context,
)


# ==========================================================
# Answer Generation Agent
#
# Generates a factually correct answer from the retrieved
# documents, using the configured LLM at temperature 0.
#
# Rules enforced through the prompt:
#   - CONTEXT ONLY (anti-hallucination)
#   - NO invented examples
#   - NO category mixing
#   - completeness for explicitly listed examples
#   - exact fallback when evidence is insufficient:
#         I don't know based on the provided document.
#
# On LLM failure (e.g. rate limiting) the agent returns a
# structured error instead of a guessed answer:
#         STATUS: ERROR / REASON: llm_rate_limit
# ==========================================================

UNKNOWN_ANSWER = (
    "I don't know based on the provided document."
)

RATE_LIMIT_ERROR = {
    "status": "ERROR",
    "reason": "LLM rate limit",
    "answer": "",
    "doc_count": 0,
}


def build_answer_prompt(
    question,
    context,
    rewritten_question=None,
    feedback=None,
):
    """
    Build the generic, subject-agnostic answer prompt.

    `feedback` (optional) carries grounding failures from a
    previous attempt so the model can revise the answer to
    remove unsupported claims.
    """

    if not rewritten_question:
        rewritten_question = question

    feedback_block = ""

    if feedback:
        feedback_block = f"""

==========================================================
PREVIOUS ATTEMPT FEEDBACK
==========================================================

Your previous answer failed grounding verification:

{feedback}

Revise the answer so that every claim is explicitly supported
by CONTEXT. Remove the unsupported content listed above. Do not
repeat the listed problems. Do not drop supported content. Do
not answer a different question.
"""

    return f"""
You are a strict RAG question-answering assistant.

You are answering questions based ONLY on the provided document,
which may be about any subject.

Your answer MUST be based ONLY on the CONTEXT below.

You have NO permission to use outside knowledge.

==========================================================
CORE RULES
==========================================================

1. Use ONLY information explicitly supported by CONTEXT.

2. If the CONTEXT contains enough information to answer the
   question, you MUST answer now. Extract the answer from
   CONTEXT. Do NOT refuse, defer, or say you don't know when
   the CONTEXT provides the answer.

3. Do NOT use your general knowledge outside CONTEXT.

4. Do NOT invent facts, names, dates, or numbers.

5. Do NOT invent examples.

6. Do NOT assume that something is an example merely because
   it appears in a table, a list, or a diagram.

7. Do NOT classify an item yourself unless the CONTEXT
   explicitly supports that classification.

8. Do NOT mix information from different categories or topics.

9. CHAT HISTORY is NOT factual evidence.

10. The REWRITTEN QUESTION is only used to understand
    what the user is asking.

11. Use the UNKNOWN response ONLY when the CONTEXT contains
    no relevant information at all. In that case answer exactly:

I don't know based on the provided document.

==========================================================
EXAMPLES RULE
==========================================================

If the user asks for examples of a category, you MUST look
for examples that the CONTEXT explicitly identifies as
belonging to that category.

Do NOT assume that every item that appears near the category
in the document is automatically an example of it.

An item appearing in a table, a list, or a diagram is NOT
automatically an example.

Only explicitly supported examples may be returned.

==========================================================
COMPLETENESS RULE
==========================================================

When the CONTEXT explicitly lists multiple examples for
the category being asked about, include ALL of those
examples that are supported by the CONTEXT.

Do not stop after finding the first example.

==========================================================
CATEGORY RULE
==========================================================

Do NOT use examples or facts from one category when
answering a question about a different category.

If the question asks about one category, answer only about
that category.

==========================================================
DEFINITION QUESTIONS
==========================================================

If the question asks for a definition, give the definition
supported by the CONTEXT and then give the explicitly
supported examples when available.

==========================================================
EXAMPLE QUESTIONS
==========================================================

If the question asks for examples of a category, give the
complete set of examples that the CONTEXT explicitly
identifies for that category.

Do not add unrelated items.

==========================================================
UNKNOWN QUESTIONS
==========================================================

Only if the CONTEXT contains no relevant information at all,
respond exactly:

I don't know based on the provided document.

==========================================================
QUESTION
==========================================================

{question}

{feedback_block}
==========================================================
REWRITTEN QUESTION
==========================================================

{rewritten_question}

==========================================================
CONTEXT
==========================================================

{context}

==========================================================
FINAL ANSWER
==========================================================

Answer the question now.

Remember:

- CONTEXT ONLY
- NO outside knowledge
- NO invented examples
- NO category mixing
- Include all explicitly supported examples
- Do not classify table fields automatically
"""


def generate_answer(
    question,
    documents,
    rewritten_question=None,
    feedback=None,
    llm=None,
):
    """
    Generate the answer for the question.

    Returns a dict:
        {
            "answer":   str,
            "status":   "OK" | "UNKNOWN" | "ERROR",
            "reason":   str | None,
            "doc_count": int,
        }
    """

    doc_count = len(documents)

    if doc_count == 0:

        return {
            "answer": UNKNOWN_ANSWER,
            "status": "UNKNOWN",
            "reason": "no evidence",
            "doc_count": 0,
        }

    context = build_context(documents)

    prompt = build_answer_prompt(
        question,
        context,
        rewritten_question=rewritten_question,
        feedback=feedback,
    )

    if llm is None:
        llm = create_llm(prefer="answer")

    try:

        response = llm.invoke(prompt)

    except ProviderUnavailableError as exc:
        # Every configured provider failed. Surface the reason
        # from the failover chain; never guess an answer.
        return {
            "status": "ERROR",
            "reason": exc.reason,
            "answer": "",
            "doc_count": doc_count,
        }

    except Exception as exc:  # noqa: BLE001
        # Most likely a rate-limit / provider failure.
        # Per spec surface a structured error, never a guess.
        return {
            "status": "ERROR",
            "reason": "LLM rate limit",
            "answer": "",
            "doc_count": doc_count,
        }

    answer = extract_response_text(response).strip()

    if answer == UNKNOWN_ANSWER:
        status = "UNKNOWN"
        reason = "insufficient evidence"
    else:
        status = "OK"
        reason = None

    return {
        "answer": answer,
        "status": status,
        "reason": reason,
        "doc_count": doc_count,
    }