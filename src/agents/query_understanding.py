import re

from src.llm import create_llm
from src.agents.utils import extract_response_text


# ==========================================================
# Query Understanding Agent
#
# Understands what the user is asking WITHOUT answering it.
#
# Responsibilities:
#   1. Detect references (pronouns / anaphora)
#   2. Produce a self-contained (standalone) question
#   3. Classify the question intent
#
# The core is deterministic. The LLM is used ONLY to rewrite
# a follow-up question when a reference is actually present
# and chat history is available.
# ==========================================================


def detect_references(question):
    """
    Return a list of reference tokens found in the question.

    A "reference" is a pronoun or demonstrative that points to
    something mentioned earlier in the conversation.
    """

    patterns = [
        r"\btheir\b",
        r"\btheirs\b",
        r"\bthey\b",
        r"\bthem\b",
        r"\bits\b",
        r"\bit\b",
        r"\bthese\b",
        r"\bthose\b",
        r"\bthis\b",
        r"\bsuch\b",
        r"\bthat\b",
        r"\bmentioned\b",
        r"\bprevious\b",
        r"\babove\b",
    ]

    matches = []

    for pattern in patterns:

        if re.search(pattern, question):
            matches.append(pattern)

    return matches


def detect_intent(question):
    """
    Classify the question intent.

    Categories:
        comparison   - asking about differences / similarities
        reasoning    - asking why / how / explanation
        examples     - asking for examples / instances
        definition   - asking what X is / define X
        follow_up    - refers to something earlier
        other        - anything else
    """

    q = str(question).strip().lower().rstrip("?")
    text = " " + q + " "

    # ------------------------------------------------------
    # Follow-up reference
    # ------------------------------------------------------

    if detect_references(question):
        return "follow_up"

    # ------------------------------------------------------
    # Comparison
    # ------------------------------------------------------

    if any(
        token in text
        for token in [
            " difference",
            " different ",
            " differences",
            " compare",
            " versus",
            " vs ",
            " similarities",
            " similarity ",
            " distinguish",
        ]
    ):
        return "comparison"

    # ------------------------------------------------------
    # Reasoning
    # ------------------------------------------------------

    if (
        text.lstrip().startswith("why ")
        or text.lstrip().startswith("how ")
        or " reason" in text
        or " because " in text
    ):
        return "reasoning"

    # ------------------------------------------------------
    # Examples
    # ------------------------------------------------------

    if any(
        token in text
        for token in [
            " example",
            " examples",
            " instance",
            " instances",
            " illustrated",
        ]
    ):
        return "examples"

    # ------------------------------------------------------
    # Definition
    # ------------------------------------------------------

    stripped = text.strip()

    if (
        stripped.startswith("what is")
        or stripped.startswith("what are")
        or stripped.startswith("what does")
        or stripped.startswith("what do")
        or stripped.startswith("define")
        or " definition" in text
        or " mean" in text
    ):
        return "definition"

    # ------------------------------------------------------
    # Follow-up reference
    # ------------------------------------------------------

    if detect_references(question):
        return "follow_up"

    return "other"


def rewrite_question(question, chat_history):
    """
    Rewrite a follow-up question into a self-contained search
    query using chat history ONLY to resolve references.
    """

    rewrite_prompt = f"""
You are a query rewriting assistant.

Your ONLY job is to rewrite the current question so that it is
self-contained.

Use CHAT HISTORY ONLY to resolve references.

Do NOT answer the question.

Do NOT add facts.

Do NOT add examples.

Do NOT change the meaning.

Return ONLY the rewritten question.

Do NOT invent or assume a specific topic. The document can be
about any subject.

Examples:

Previous question:
What is the capital of France?

Current question:
What are its main attractions?

Rewritten question:
What are the main attractions of the capital of France?

Previous question:
What are the benefits of exercise?

Current question:
What are their drawbacks?

Rewritten question:
What are the drawbacks of exercise?

Previous question:
What is a database?

Current question:
What are its components?

Rewritten question:
What are the components of a database?

CHAT HISTORY:
{chat_history}

CURRENT QUESTION:
{question}

REWRITTEN QUESTION:
"""

    llm = create_llm()

    try:

        response = llm.invoke(rewrite_prompt)

    except Exception:  # noqa: BLE001
        # Rewriting is best-effort. If the providers are down,
        # keep the original question so the flow still works.
        return question

    return extract_response_text(response).strip()


def understand_query(question, chat_history=""):
    """
    Understand the user's question without answering it.

    Returns a dict:
        {
            "standalone_question": self-contained question,
            "intent":              intent category,
            "detected_references": list of reference patterns,
            "rewrote":             bool,
            "history_used":        bool,
        }
    """

    original = str(question).strip()

    references = detect_references(original)

    history_used = bool(chat_history and chat_history.strip())

    standalone_question = original
    rewrote = False

    # ------------------------------------------------------
    # Rewrite ONLY when a reference is present and we have a
    # chat history to resolve it against.
    # ------------------------------------------------------

    if history_used and references:

        standalone_question = rewrite_question(
            original,
            chat_history,
        )

        rewrote = (
            standalone_question != original
        )

    intent = detect_intent(standalone_question)

    return {
        "standalone_question": standalone_question,
        "intent": intent,
        "detected_references": references,
        "rewrote": rewrote,
        "history_used": history_used,
    }