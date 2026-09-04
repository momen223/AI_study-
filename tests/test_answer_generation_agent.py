# ==========================================================
# ANSWER GENERATION AGENT TEST
#
# Tests src/agents/answer_generation.generate_answer()
#
#  - grounded answer for a definition question
#  - grounded answer for a category question
#  - empty evidence -> exact fallback
#  - rate-limit / provider error -> structured ERROR
#    (simulated with a fake LLM that raises)
# ==========================================================

from src.cromaDB import load_vectorstore
from src.embeddings import create_embedding_model
from src.agents.retrieval import retrieve
from src.agents.answer_generation import (
    generate_answer,
    build_answer_prompt,
    UNKNOWN_ANSWER,
)


class FakeRaisingLLM:
    """Simulates a provider error (e.g. rate limit)."""

    def invoke(self, prompt):
        raise Exception("429 Too Many Requests")


class FakeOkLLM:
    """Returns a canned grounded answer."""

    def invoke(self, prompt):
        class Response:
            content = (
                "A fact table is a table that stores numerical "
                "measures in a data warehouse."
            )
        return Response()


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
    print("ANSWER GENERATION AGENT TEST")
    print("=" * 75)

    # ------------------------------------------------------
    # No documents -> exact fallback (no LLM call)
    # ------------------------------------------------------

    result = generate_answer(
        "What is a fact table?",
        [],
    )

    check(
        "no evidence -> UNKNOWN status",
        result["status"] == "UNKNOWN",
    )

    check(
        "no evidence -> exact fallback text",
        result["answer"] == UNKNOWN_ANSWER,
    )

    check(
        "no evidence -> reason present",
        result["reason"] == "no evidence",
    )

    # ------------------------------------------------------
    # Real pipeline: answer a definition question
    # ------------------------------------------------------

    embeddings = create_embedding_model()

    vectorstore = load_vectorstore(embeddings)

    retrieval_result = retrieve(
        vectorstore,
        "What is a fact table?",
    )

    documents = retrieval_result["documents"]

    result = generate_answer(
        "What is a fact table?",
        documents,
    )

    check(
        "definition answer status OK",
        result["status"] == "OK",
    )

    check(
        "definition answer non-empty",
        bool(result["answer"].strip()),
    )

    check(
        "definition answer is grounded",
        "fact table" in result["answer"].lower(),
    )

    check(
        "did not fall back",
        result["answer"] != UNKNOWN_ANSWER,
    )

    check(
        "doc_count reported",
        result["doc_count"] == len(documents),
    )

    # ------------------------------------------------------
    # Real pipeline: answer a category question
    # ------------------------------------------------------

    retrieval_result = retrieve(
        vectorstore,
        "What are the examples of fully additive measures?",
    )

    result = generate_answer(
        "What are the examples of fully additive measures?",
        retrieval_result["documents"],
    )

    check(
        "examples answer status OK",
        result["status"] == "OK",
    )

    check(
        "examples answer grounded",
        "sales amount" in result["answer"].lower(),
    )

    # ------------------------------------------------------
    # Rate limit / provider failure
    # ------------------------------------------------------

    result = generate_answer(
        "What is a fact table?",
        documents,
        llm=FakeRaisingLLM(),
    )

    check(
        "rate limit -> ERROR status",
        result["status"] == "ERROR",
    )

    check(
        "rate limit -> REASON present",
        result["reason"] is not None,
    )

    check(
        "rate limit -> no guessed answer",
        result["answer"] == "",
    )

    # ------------------------------------------------------
    # Fake OK LLM path
    # ------------------------------------------------------

    result = generate_answer(
        "What is a fact table?",
        documents,
        llm=FakeOkLLM(),
    )

    check(
        "fake OK llm -> OK status",
        result["status"] == "OK",
    )

    check(
        "fake OK llm -> answer returned",
        result["answer"]
        == "A fact table is a table that stores numerical "
        "measures in a data warehouse.",
    )

    # ------------------------------------------------------
    # Prompt builder sanity
    # ------------------------------------------------------

    prompt = build_answer_prompt(
        "What is a fact table?",
        "[PAGE 5]\nsome evidence",
    )

    check(
        "prompt contains question",
        "What is a fact table?" in prompt,
    )

    check(
        "prompt contains context",
        "[PAGE 5]\nsome evidence" in prompt,
    )

    check(
        "prompt subject-agnostic",
        "data warehousing lecture" not in prompt.lower(),
    )

    # ------------------------------------------------------

    print("\n" + "=" * 75)
    print(f"ANSWER GENERATION AGENT TEST SUMMARY")
    print(f"TOTAL:     {total}")
    print(f"FAILURES:  {failures}")
    print("=" * 75)

    if failures == 0:
        print("\nALL ANSWER GENERATION AGENT TESTS PASSED")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())