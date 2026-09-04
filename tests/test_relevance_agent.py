# ==========================================================
# RELEVANCE / EVIDENCE AGENT TEST
#
# Tests src/agents/relevance.check_relevance_evidence()
#
#  - correct RELEVANT verdicts for answerable questions
#  - correct NOT_RELEVANT verdicts for unrelated questions
#  - non-empty reason on every decision
#  - question/context overlap signal present
#  - works with explicitly provided documents
# ==========================================================

from src.cromaDB import load_vectorstore
from src.embeddings import create_embedding_model
from src.agents.relevance import check_relevance_evidence
from src.agents.retrieval import retrieve
from src.config import RELEVANCE_CHECK_K


def run():

    failures = 0
    total = 0

    def check(name, condition):
        nonlocal failures, total
        total += 1
        status = "PASS" if condition else "FAIL"
        if not condition:
            failures += 1
        print(f"{status:5s} | {name}")

    print("\n")
    print("=" * 75)
    print("RELEVANCE / EVIDENCE AGENT TEST")
    print("=" * 75)

    embeddings = create_embedding_model()

    vectorstore = load_vectorstore(embeddings)

    # ------------------------------------------------------
    # Answerable questions -> RELEVANT
    # ------------------------------------------------------

    relevant_queries = [
        "What is a fact table?",
        "What are fully additive measures?",
        "Why cannot Profit Margin percent be summed?",
        "What is the difference between fully additive and "
        "semi-additive measures?",
    ]

    for query in relevant_queries:

        result = check_relevance_evidence(
            vectorstore,
            query,
        )

        check(
            f"RELEVANT: {query[:45]}",
            result["verdict"] == "RELEVANT",
        )

    # ------------------------------------------------------
    # Unrelated questions -> NOT_RELEVANT
    # ------------------------------------------------------

    not_relevant_queries = [
        "What is the capital of France?",
        "What does quantum physics mean?",
        "What is 2+2?",
        "Who invented the telephone?",
    ]

    for query in not_relevant_queries:

        result = check_relevance_evidence(
            vectorstore,
            query,
        )

        check(
            f"NOT_RELEVANT: {query[:45]}",
            result["verdict"] == "NOT_RELEVANT",
        )

    # ------------------------------------------------------
    # Every result has a reason
    # ------------------------------------------------------

    for query in relevant_queries + not_relevant_queries:

        result = check_relevance_evidence(
            vectorstore,
            query,
        )

        check(
            f"reason present: {query[:35]}",
            bool(result["reason"].strip()),
        )

    # ------------------------------------------------------
    # Overlap signal structure
    # ------------------------------------------------------

    result = check_relevance_evidence(
        vectorstore,
        "What is a fact table?",
    )

    overlap = result["overlap"]

    check(
        "overlap dict present",
        isinstance(overlap, dict),
    )

    check(
        "overlap keys complete",
        set(overlap.keys()) == {
            "query_words",
            "matched_words",
            "overlap_ratio",
            "docs_with_match",
            "doc_count",
        },
    )

    france = check_relevance_evidence(
        vectorstore,
        "What is the capital of France?",
    )

    check(
        "relevant overlap > unrelated overlap",
        overlap["overlap_ratio"]
        > france["overlap"]["overlap_ratio"],
    )

    # ------------------------------------------------------
    # Works with explicitly provided documents
    # ------------------------------------------------------

    retrieval_result = retrieve(
        vectorstore,
        "What is a fact table?",
    )

    explicit = check_relevance_evidence(
        vectorstore,
        "What is a fact table?",
        documents=retrieval_result["documents"],
    )

    check(
        "explicit documents accepted",
        explicit["verdict"] == "RELEVANT",
    )

    # ------------------------------------------------------

    print("\n" + "=" * 75)
    print(f"RELEVANCE / EVIDENCE AGENT TEST SUMMARY")
    print(f"TOTAL:     {total}")
    print(f"FAILURES:  {failures}")
    print("=" * 75)

    if failures == 0:
        print("\nALL RELEVANCE / EVIDENCE AGENT TESTS PASSED")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())