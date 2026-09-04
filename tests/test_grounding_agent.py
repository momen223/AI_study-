# ==========================================================
# GROUNDING / VERIFICATION AGENT TEST
#
# Tests src/agents/grounding.verify_grounding()
#
#  - UNKNOWN fallback -> SKIPPED/PASS (nothing to verify)
#  - grounded answer -> PASS (deterministic + live LLM)
#  - hallucinated answer -> FAIL even if the verifier LLM
#    claims PASS (deterministic gate dominates)
#  - unattested numbers -> FAIL
#  - no documents -> FAIL
#  - fake LLM crash -> graceful, still returns structured dict
# ==========================================================

from src.cromaDB import load_vectorstore
from src.embeddings import create_embedding_model
from src.agents.retrieval import retrieve
from src.agents.answer_generation import UNKNOWN_ANSWER
from src.agents.grounding import verify_grounding


class FakePassLLM:
    """Reportedly says PASS regardless."""

    def invoke(self, prompt):
        class Response:
            content = "PASS"
        return Response()


class FakeRaisingLLM:
    """Simulates a provider failure during verification."""

    def invoke(self, prompt):
        raise Exception("429 Too Many Requests")


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
    print("GROUNDING / VERIFICATION AGENT TEST")
    print("=" * 75)

    embeddings = create_embedding_model()

    vectorstore = load_vectorstore(embeddings)

    retrieval_result = retrieve(
        vectorstore,
        "What is a fact table?",
    )

    documents = retrieval_result["documents"]

    # ------------------------------------------------------
    # UNKNOWN fallback -> SKIPPED
    # ------------------------------------------------------

    result = verify_grounding(
        "What is a fact table?",
        UNKNOWN_ANSWER,
        documents,
        llm=FakePassLLM(),
    )

    check(
        "fallback -> SKIPPED",
        result["status"] == "SKIPPED",
    )

    check(
        "fallback -> PASS verdict",
        result["verdict"] == "PASS",
    )

    # ------------------------------------------------------
    # Grounded answer -> PASS
    # ------------------------------------------------------

    grounded_answer = (
        "A fact table contains the numeric measures of a "
        "business process, such as sales amount, and foreign "
        "keys to the surrounding dimension tables."
    )

    result = verify_grounding(
        "What is a fact table?",
        grounded_answer,
        documents,
        llm=FakePassLLM(),
    )

    check(
        "grounded answer -> PASS",
        result["verdict"] == "PASS",
    )

    check(
        "grounded answer -> no reasons",
        result["reasons"] == [],
    )

    # ------------------------------------------------------
    # Hallucinated answer -> FAIL even if LLM says PASS
    # (deterministic gate dominates)
    # ------------------------------------------------------

    hallucinated = (
        "A fact table was invented by Bill Inmon in 1990 and "
        "stores 7 facts per row."
    )

    result = verify_grounding(
        "What is a fact table?",
        hallucinated,
        documents,
        llm=FakePassLLM(),
    )

    check(
        "hallucinated answer -> FAIL",
        result["verdict"] == "FAIL",
    )

    check(
        "hallucinated -> reasons present",
        bool(result["reasons"]),
    )

    check(
        "hallucinated name flagged",
        any(
            "inmon" in reason.lower()
            or "bill" in reason.lower()
            for reason in result["reasons"]
        ),
    )

    # ------------------------------------------------------
    # Unattested statistics -> FAIL
    # ------------------------------------------------------

    numerical = "A fact table stores exactly 42 measures."

    result = verify_grounding(
        "What is a fact table?",
        numerical,
        documents,
        llm=FakePassLLM(),
    )

    check(
        "unattested number -> FAIL",
        result["verdict"] == "FAIL",
    )

    # ------------------------------------------------------
    # No documents -> FAIL
    # ------------------------------------------------------

    result = verify_grounding(
        "What is a fact table?",
        "A fact table is a table",
        [],
        llm=FakePassLLM(),
    )

    check(
        "no documents -> FAIL",
        result["verdict"] == "FAIL",
    )

    # ------------------------------------------------------
    # Verifier LLM failure is graceful
    # ------------------------------------------------------

    result = verify_grounding(
        "What is a fact table?",
        grounded_answer,
        documents,
        llm=FakeRaisingLLM(),
    )

    check(
        "verifier crash still returns dict",
        isinstance(result, dict),
    )

    check(
        "verifier crash sets llm_error",
        result["llm_error"] is True,
    )

    check(
        "verifier crash keeps verdict structure",
        result["verdict"] in ("PASS", "FAIL"),
    )

    # ------------------------------------------------------
    # Page citations copied from context are NOT statistics
    # (regression: answers that cite "(Page n)" must not be
    #  flagged as hallucinated numbers)
    # ------------------------------------------------------

    snippet = documents[0].page_content.strip().split(".")[0]

    citation_answer = (
        f"{snippet}. This information appears on Page "
        f"{retrieval_result['metadata'][0].get('page', 1)}."
    )

    result = verify_grounding(
        "What is a fact table?",
        citation_answer,
        documents,
        llm=FakePassLLM(),
    )

    check(
        "page citation not flagged as number",
        all(
            "unattested numbers" not in reason
            for reason in result["reasons"]
        ),
    )

    check(
        "page citation answer -> PASS",
        result["verdict"] == "PASS",
    )

    # ------------------------------------------------------
    # Live LLM end-to-end on a generated answer
    # (assert structural self-consistency, not one verdict:
    #  the generator may legitimately hallucinate and the
    #  verifier may legitimately catch it)
    # ------------------------------------------------------

    from src.agents.answer_generation import generate_answer

    generation = generate_answer(
        "What is a fact table?",
        documents,
    )

    check(
        "answer generation OK before grounding",
        generation["status"] == "OK",
    )

    result = verify_grounding(
        "What is a fact table?",
        generation["answer"],
        documents,
    )

    check(
        "live verification returns a verdict",
        result["verdict"] in ("PASS", "FAIL"),
    )

    check(
        "PASS has no reasons",
        not (result["verdict"] == "PASS" and result["reasons"]),
    )

    check(
        "FAIL has reasons",
        not (result["verdict"] == "FAIL" and not result["reasons"]),
    )

    check(
        "live verification has no llm_error",
        result["llm_error"] is False,
    )

    # ------------------------------------------------------

    print("\n" + "=" * 75)
    print(f"GROUNDING / VERIFICATION AGENT TEST SUMMARY")
    print(f"TOTAL:     {total}")
    print(f"FAILURES:  {failures}")
    print("=" * 75)

    if failures == 0:
        print("\nALL GROUNDING / VERIFICATION AGENT TESTS PASSED")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())