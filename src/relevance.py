from src.config import (
    RETRIEVAL_DISTANCE_THRESHOLD,
    STRONG_RELEVANCE_THRESHOLD,
    RELEVANCE_CHECK_K,
    MIN_STRONG_CHUNKS,
    MIN_RELEVANT_CHUNKS,
    RELEVANCE_BAND,
)
from src.retriever import similarity_search_with_scores


# ==========================================================
# Multi-signal relevance check.
#
# A single hard-coded distance threshold is NOT enough.
# This function combines several weak signals:
#
#   1. Best similarity score
#   2. Number of strong chunks (<= STRONG_RELEVANCE_THRESHOLD)
#   3. Number of relevant chunks (<= RETRIEVAL_DISTANCE_THRESHOLD)
#   4. Evidence coverage (how many of the top-k chunks pass)
#
# Chroma distance semantics:
#   LOWER = MORE SIMILAR
#   HIGHER = LESS SIMILAR
# ==========================================================


def check_relevance(vectorstore, query):
    """
    Decide whether the query is answerable from the vectorstore.

    Returns a dict:
        {
            "verdict":     "RELEVANT" | "NOT_RELEVANT",
            "reason":      human-readable explanation,
            "best_score":  float,
            "strong_count": int,
            "relevant_count": int,
            "scores":      list of top-k distances,
        }
    """

    results = similarity_search_with_scores(
        vectorstore,
        query,
        k=RELEVANCE_CHECK_K,
    )

    if not results:
        return {
            "verdict": "NOT_RELEVANT",
            "reason": "No documents retrieved.",
            "best_score": None,
            "strong_count": 0,
            "relevant_count": 0,
            "scores": [],
        }

    scores = [score for _, score in results]

    best_score = min(scores)

    strong_count = sum(
        1 for score in scores
        if score <= STRONG_RELEVANCE_THRESHOLD
    )

    relevant_count = sum(
        1 for score in scores
        if score <= RETRIEVAL_DISTANCE_THRESHOLD
    )

    # ------------------------------------------------------
    # Decision logic
    #
    # Signal 1: strong single match
    #   RELEVANT if enough chunks are strongly similar.
    #
    # Signal 2: evidence coverage
    #   RELEVANT if the BEST chunk is near-strong AND several
    #   chunks corroborate it. Prevents a single mediocre hit
    #   from passing just because it is under the main
    #   threshold.
    # ------------------------------------------------------

    if strong_count >= MIN_STRONG_CHUNKS:

        verdict = "RELEVANT"
        reason = (
            f"{strong_count} strong chunk(s) "
            f"(best={best_score:.4f})"
        )

    elif (
        best_score
        <= STRONG_RELEVANCE_THRESHOLD + RELEVANCE_BAND
        and relevant_count >= MIN_RELEVANT_CHUNKS
    ):

        verdict = "RELEVANT"
        reason = (
            f"Strong evidence coverage "
            f"(best={best_score:.4f}, "
            f"relevant={relevant_count}, "
            f"strong={strong_count})"
        )

    else:

        verdict = "NOT_RELEVANT"
        reason = (
            f"Insufficient evidence "
            f"(best={best_score:.4f}, "
            f"relevant={relevant_count})"
        )

    return {
        "verdict": verdict,
        "reason": reason,
        "best_score": best_score,
        "strong_count": strong_count,
        "relevant_count": relevant_count,
        "scores": scores,
    }