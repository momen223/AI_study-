# ==========================================================
# RETRIEVAL AGENT TEST
#
# Tests src/agents/retrieval.retrieve()
#
#  - returns the configured number of documents
#  - returns metadata and page fields
#  - returns a similarity-score snapshot
#  - MMR diversity: relevant query returns relevant docs
#  - still returns something for an unrelated query
#    (relevance rejection happens in Agent 4)
# ==========================================================

from src.cromaDB import load_vectorstore
from src.embeddings import create_embedding_model
from src.agents.retrieval import retrieve
from src.config import RETRIEVER_K


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
    print("RETRIEVAL AGENT TEST")
    print("=" * 75)

    embeddings = create_embedding_model()

    vectorstore = load_vectorstore(embeddings)

    # ------------------------------------------------------
    # Relevant query
    # ------------------------------------------------------

    result = retrieve(
        vectorstore,
        "What is a fact table?",
    )

    docs = result["documents"]

    check(
        "returns k documents",
        len(docs) == RETRIEVER_K,
    )

    check(
        "metadata aligned with documents",
        len(result["metadata"]) == len(docs),
    )

    check(
        "pages aligned with documents",
        len(result["pages"]) == len(docs),
    )

    check(
        "all metadata are dicts",
        all(
            isinstance(m, dict)
            for m in result["metadata"]
        ),
    )

    check(
        "scores snapshot is non-empty",
        len(result["scores"]) > 0,
    )

    check(
        "query echoed back",
        result["query"] == "What is a fact table?",
    )

    check(
        "no empty documents returned",
        all(doc.page_content.strip() for doc in docs),
    )

    # ------------------------------------------------------
    # Same content present in retrieved context.
    # ------------------------------------------------------

    combined = " ".join(
        doc.page_content.lower()
        for doc in docs
    )

    check(
        "retrieved content mentions fact tables",
        "fact table" in combined,
    )

    # ------------------------------------------------------
    # Custom k override
    # ------------------------------------------------------

    result3 = retrieve(
        vectorstore,
        "What is a fact table?",
        k=3,
    )

    check(
        "k override respected",
        len(result3["documents"]) == 3,
    )

    # ------------------------------------------------------
    # Unrelated query still returns something
    # (rejection is Agent 4's job)
    # ------------------------------------------------------

    unrelated = retrieve(
        vectorstore,
        "What is the capital of France?",
    )

    check(
        "unrelated query still returns docs",
        len(unrelated["documents"]) > 0,
    )

    # ------------------------------------------------------

    print("\n" + "=" * 75)
    print(f"RETRIEVAL AGENT TEST SUMMARY")
    print(f"TOTAL:     {total}")
    print(f"FAILURES:  {failures}")
    print("=" * 75)

    if failures == 0:
        print("\nALL RETRIEVAL AGENT TESTS PASSED")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())