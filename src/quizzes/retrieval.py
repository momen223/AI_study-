# ==========================================================
# Quiz context retrieval.
#
# Reuses the existing retrieval agent and Chroma retriever but
# asks for MORE chunks than a typical chat query, because each
# MCQ item needs enough grounding for its stem, correct option
# and explanation. No query-understanding / relevance / MMR logic
# is duplicated or altered here -- the chat pipeline is untouched.
# ==========================================================

from src.agents import retrieval as agent_retrieval
from src.agents.utils import build_context
from src.config import QUIZ_RETRIEVAL_K, QUIZ_FETCH_K


def retrieve_quiz_context(vectorstore, topic, k=None, fetch_k=None):
    """
    Retrieve the document chunks that can ground a quiz for `topic`.

    Returns:
        {
            "documents":  list of Document,
            "metadata":   list of metadata dicts,
            "pages":      list of page numbers,
            "scores":     similarity distances (lower = more similar),
            "context":    str (build_context representation),
            "k":          effective k,
            "query":      the topic used,
        }

    The returned context always reflects what was actually in the
    corpus, so any later validation can compare generated text
    against it deterministically.
    """
    if k is None:
        k = QUIZ_RETRIEVAL_K
    if fetch_k is None:
        fetch_k = QUIZ_FETCH_K

    result = agent_retrieval.retrieve(
        vectorstore,
        topic,
        k=k,
        fetch_k=fetch_k,
        lambda_mult=0.95,
    )

    context = build_context(result["documents"])

    return {
        **result,
        "context": context,
    }


def find_evidence(topic, documents):
    """
    Return the single most supportive chunk among `documents` for the
    topic's content words, or None.

    Uses lexical overlap between the topic's content words and each
    document's page content (the same signal family as the relevance
    agent), returning the doc with the highest ratio. This is used to
    pick the evidence snippet that a generated question must be
    consistent with.
    """
    from src.agents.relevance import _content_words

    words = _content_words(topic or "")

    if not words:
        return None

    best = None
    best_ratio = 0.0

    combined_all = []

    for document in documents:

        content = document.page_content or ""
        combined_all.append((document, content))

        matched = sum(
            1 for word in words if word in content.lower()
        )
        ratio = matched / len(words)

        if ratio > best_ratio:
            best_ratio = ratio
            best = document

    if best is None:
        return None

    return best
