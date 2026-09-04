# ==========================================================
# QUERY UNDERSTANDING AGENT TEST
#
# Unit tests (deterministic, no LLM):
#   - reference detection
#   - intent classification
#   - no-history = no rewrite
#
# Integration test (needs LLM):
#   - follow-up reference resolution
# ==========================================================

from src.agents.query_understanding import (
    detect_references,
    detect_intent,
    understand_query,
)


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
    print("QUERY UNDERSTANDING AGENT TEST")
    print("=" * 75)

    # ------------------------------------------------------
    # Reference detection
    # ------------------------------------------------------

    check(
        "their detected",
        detect_references("What are their examples?")
        == [r"\btheir\b"],
    )

    check(
        "no references in standalone question",
        detect_references("What are fully additive measures?")
        == [],
    )

    check(
        "its detected",
        bool(detect_references("What are its components?")),
    )

    # ------------------------------------------------------
    # Intent classification
    # ------------------------------------------------------

    check(
        "definition intent",
        detect_intent("What are fully additive measures?")
        == "definition",
    )

    check(
        "examples intent",
        detect_intent("What are the examples of fully additive measures?")
        == "examples",
    )

    check(
        "comparison intent",
        detect_intent(
            "What is the difference between fully additive, "
            "semi-additive, and non-additive measures?"
        ) == "comparison",
    )

    check(
        "reasoning intent",
        detect_intent("Why cannot inventory be summed across time?")
        == "reasoning",
    )

    check(
        "follow-up intent",
        detect_intent("What are their examples?")
        == "follow_up",
    )

    # ------------------------------------------------------
    # No history = no rewrite
    # ------------------------------------------------------

    result = understand_query("What are fully additive measures?")

    check(
        "no history keeps question",
        result["standalone_question"] == "What are fully additive measures?",
    )

    check(
        "no history, no rewrite",
        result["rewrote"] is False,
    )

    check(
        "no history, history_used false",
        result["history_used"] is False,
    )

    # ------------------------------------------------------
    # No reference + history = no LLM rewrite
    # ------------------------------------------------------

    history = "User: What are fully additive measures?\nAssistant: ..."

    result = understand_query(
        "What are their examples?",
        chat_history=history,
    )

    # the question below has NO reference -> no rewrite needed
    result = understand_query(
        "What are the examples of semi-additive measures?",
        chat_history=history,
    )

    check(
        "self-contained + history = no rewrite",
        result["rewrote"] is False,
    )

    check(
        "self-contained + history = history used",
        result["history_used"] is True,
    )

    # ------------------------------------------------------
    # LLM integration: resolve a real follow-up
    # ------------------------------------------------------

    history = (
        "User: What are fully additive measures?\n"
        "Assistant: Fully additive measures are numeric facts "
        "that can be summed across all dimensions."
    )

    result = understand_query(
        "What are their examples?",
        chat_history=history,
    )

    standalone = result["standalone_question"].lower()

    check(
        "follow-up resolved to standalone",
        "fully additive" in standalone,
    )

    check(
        "follow-up intent after rewrite is examples",
        result["intent"] == "examples",
    )

    # ------------------------------------------------------

    print("\n" + "=" * 75)
    print(f"QUERY UNDERSTANDING TEST SUMMARY")
    print(f"TOTAL:     {total}")
    print(f"FAILURES:  {failures}")
    print("=" * 75)

    if failures == 0:
        print("\nALL QUERY UNDERSTANDING TESTS PASSED")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())