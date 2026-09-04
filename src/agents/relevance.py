import re

from src.relevance import check_relevance
from src.retriever import similarity_search_with_scores
from src.config import RELEVANCE_CHECK_K


# ==========================================================
# Relevance / Evidence Agent
#
# Decides whether there is enough evidence to answer the
# question. Must NOT rely on a single similarity score.
#
# Signal set:
#   1. Best similarity score
#   2. Number of strong chunks
#   3. Number of relevant chunks
#   4. Evidence coverage (fraction of top-k chunks that pass)
#   5. Question / context relationship (lexical overlap
#      between the query's content words and the actual
#      retrieved documents)
#
# Output:
#   RELEVANT | NOT_RELEVANT  + reason
# ==========================================================

STOPWORDS = {
    "a", "an", "the", "is", "are", "do", "does", "did",
    "what", "who", "when", "where", "which", "why", "how",
    "of", "in", "on", "at", "to", "for", "from", "with",
    "and", "or", "but", "not", "can", "cannot", "be", "by",
    "it", "its", "their", "them", "they", "this", "that",
    "these", "those", "give", "me", "their", "please",
    "mean", "means", "based", "provided", "document",
    "against", "across", "over", "list", "tell", "explain",
    "about",
}

# ------------------------------------------------------
# Basis-of-answer fallback string
# ------------------------------------------------------

UNKNOWN_ANSWER = (
    "I don't know based on the provided document."
)


def _content_words(query):
    """
    Return the content words of the query, case-folded,
    with stopwords removed.
    """

    words = re.findall(r"[a-zA-Z0-9]+", query.lower())

    return [
        word
        for word in words
        if word not in STOPWORDS
    ]


def _evidence_overlap(query, documents):
    """
    Measure the question / context relationship.

    Returns a dict:
        {
            "query_words":      int,
            "matched_words":    int,
            "overlap_ratio":    float (0.0 - 1.0),
            "docs_with_match":  int,
            "doc_count":        int,
        }
    """

    words = _content_words(query)

    if not words:
        return {
            "query_words": 0,
            "matched_words": 0,
            "overlap_ratio": 0.0,
            "docs_with_match": 0,
            "doc_count": len(documents),
        }

    combined = " ".join(
        document.page_content.lower()
        for document in documents
    )

    matched = sum(
        1
        for word in words
        if word in combined
    )

    docs_with_match = sum(
        1
        for document in documents
        if any(
            word in document.page_content.lower()
            for word in words
        )
    )

    return {
        "query_words": len(words),
        "matched_words": matched,
        "overlap_ratio": matched / len(words),
        "docs_with_match": docs_with_match,
        "doc_count": len(documents),
    }


def check_relevance_evidence(
    vectorstore,
    query,
    documents=None,
):
    """
    Decide whether the query is answerable.

    Primary decision: multi-signal vector check
    (best similarity + strong count + relevant count +
     evidence coverage among the top-k chunks).

    Supplementary signal: lexical question/context overlap
    measured against the actual retrieved documents.

    Returns a dict:
        {
            "verdict":        "RELEVANT" | "NOT_RELEVANT",
            "reason":         str,
            "best_score":     float | None,
            "strong_count":   int,
            "relevant_count": int,
            "scores":         list of float,
            "overlap":        dict (question/context signal),
        }
    """

    vector_verdict = check_relevance(
        vectorstore,
        query,
    )

    if documents is None:

        docs = [
            document
            for document, _ in similarity_search_with_scores(
                vectorstore,
                query,
                k=RELEVANCE_CHECK_K,
            )
        ]

    else:

        docs = documents

    overlap = _evidence_overlap(query, docs)

    return {
        "verdict": vector_verdict["verdict"],
        "reason": vector_verdict["reason"],
        "best_score": vector_verdict["best_score"],
        "strong_count": vector_verdict["strong_count"],
        "relevant_count": vector_verdict["relevant_count"],
        "scores": vector_verdict["scores"],
        "overlap": overlap,
    }