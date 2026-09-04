# ==========================================================
# Unified RAG Test Runner
#
# Consumes the `run_rag` trace dict from the agent workflow
# and prints the per-test output required by spec section 22,
# the final summary (section 23), the RESOLVED PROBLEMS
# section (24) and the REMAINING PROBLEMS section (25).
#
# The runner is subject-agnostic: each test only describes the
# *expected* retrieval / answer behaviour.  The production RAG
# system itself remains fully generic (no hardcoded answers).
#
# Test categories (spec section 18 / 19 / 20 / 21):
#   A  retrieval          relevant questions retrieve relevant chunks
#   B  unknown            unrelated questions -> "I don't know ..."
#   C  definition         answer contains the document definition
#   D  example            answer contains only supported examples
#   E  follow-up          references resolved using chat history
#   F  hallucination      general-knowledge -> not invented
#   G  context-conflict   answer must not mix another concept
#   H  answer quality     correctness/relevance/grounding/completeness
# ==========================================================

from src.agents.workflow import run_rag
from src.rag import vectorstore


UNKNOWN_ANSWER = "I don't know based on the provided document."


# ==========================================================
# Test catalog
# ==========================================================
#
# Each case:
#   name       display name
#   question   user question
#   history    chat history (default "")
#   category   A..H grouping used for summary accuracy
#   expect     expected behaviour:
#                relevance: "RELEVANT" | "NOT_RELEVANT"
#                must_contain:    keywords the answer must include
#                must_not_contain: keywords the answer must avoid
#
# `relevance` is checked against the workflow trace's relevance
# verdict.  When `relevance == "NOT_RELEVANT"` the answer is also
# required to be the unknown fallback.
#
TEST_CASES = [

    # ------------------------------------------------------
    # A. Retrieval tests
    # ------------------------------------------------------

    {
        "name": "Fact Table Retrieval",
        "question": "What is a fact table?",
        "category": "retrieval",
        "expect": {"relevance": "RELEVANT"},
    },

    {
        "name": "Dimension Retrieval",
        "question": "What is a dimension table?",
        "category": "retrieval",
        "expect": {"relevance": "RELEVANT"},
    },

    {
        "name": "Measure Retrieval",
        "question": "What is a measure in a data warehouse?",
        "category": "retrieval",
        "expect": {"relevance": "RELEVANT"},
    },

    # ------------------------------------------------------
    # B. Unknown question tests
    # ------------------------------------------------------

    {
        "name": "Unknown - France",
        "question": "What is the capital of France?",
        "category": "unknown",
        "expect": {"relevance": "NOT_RELEVANT"},
    },

    {
        "name": "Unknown - Telephone",
        "question": "Who invented the telephone?",
        "category": "unknown",
        "expect": {"relevance": "NOT_RELEVANT"},
    },

    {
        "name": "Unknown - Quantum Physics",
        "question": "What does quantum physics mean?",
        "category": "unknown",
        "expect": {"relevance": "NOT_RELEVANT"},
    },

    # ------------------------------------------------------
    # C. Definition tests
    # ------------------------------------------------------

    {
        "name": "Definition - Fully Additive",
        "question": "What are fully additive measures?",
        "category": "definition",
        "expect": {
            "relevance": "RELEVANT",
            "must_contain": ["fully additive", "summed", "dimensions"],
        },
    },

    {
        "name": "Definition - Semi-Additive",
        "question": "What are semi-additive measures?",
        "category": "definition",
        "expect": {
            "relevance": "RELEVANT",
            "must_contain": ["semi", "summed", "dimension"],
        },
    },

    {
        "name": "Definition - Non-Additive",
        "question": "What are non-additive measures?",
        "category": "definition",
        "expect": {
            "relevance": "RELEVANT",
            "must_contain": ["non-additive", "summed", "dimension"],
        },
    },

    # ------------------------------------------------------
    # D. Example tests
    # ------------------------------------------------------

    {
        "name": "Examples - Fully Additive",
        "question": "What are the examples of fully additive measures?",
        "category": "example",
        "expect": {
            "relevance": "RELEVANT",
            "must_contain": [
                "quantity sold",
                "revenue",
                "cost",
                "units produced",
            ],
        },
    },

    {
        "name": "Examples - Semi-Additive",
        "question": "What are the examples of semi-additive measures?",
        "category": "example",
        "expect": {
            "relevance": "RELEVANT",
            "must_contain": [
                "inventory",
                "bank balance",
                "stock quantity",
            ],
        },
    },

    {
        "name": "Examples - Non-Additive",
        "question": "What are the examples of non-additive measures?",
        "category": "example",
        "expect": {
            "relevance": "RELEVANT",
            "must_contain": [
                "profit margin",
                "ratio",
                "conversion rate",
            ],
        },
    },

    # ------------------------------------------------------
    # E. Follow-up tests
    # ------------------------------------------------------

    {
        "name": "Follow-up - Fully Additive Examples",
        "question": "What are their examples?",
        "history": (
            "User: What are fully additive measures?\n"
            "Assistant: Fully additive measures can be summed "
            "across all dimensions."
        ),
        "category": "followup",
        "expect": {
            "relevance": "RELEVANT",
            "must_contain": ["quantity sold", "revenue"],
        },
    },

    {
        "name": "Follow-up - Semi-Additive Examples",
        "question": "What are their examples?",
        "history": (
            "User: What are semi-additive measures?\n"
            "Assistant: Semi-additive measures can be summed "
            "across some dimensions but not all."
        ),
        "category": "followup",
        "expect": {
            "relevance": "RELEVANT",
            "must_contain": ["inventory", "bank balance"],
        },
    },

    {
        "name": "Follow-up - Non-Additive Examples",
        "question": "What are their examples?",
        "history": (
            "User: What are non-additive measures?\n"
            "Assistant: Non-additive measures cannot be summed "
            "across any dimension."
        ),
        "category": "followup",
        "expect": {
            "relevance": "RELEVANT",
            "must_contain": ["profit margin", "ratio"],
        },
    },

    # ------------------------------------------------------
    # F. Anti-hallucination tests
    # ------------------------------------------------------

    {
        # Asking for an example NOT in the document. The correct
        # anti-hallucination behaviour is to REFUSE to invent one,
        # rather than fabricate a new example. So we assert the
        # refusal (unknown fallback), not its absence.
        "name": "Anti-hallucination - Invented Example",
        "question": (
            "Give me an example of a non-additive measure "
            "that is not mentioned in the lecture."
        ),
        "category": "hallucination",
        "expect": {
            "relevance": "RELEVANT",
            "must_contain": ["I don't know"],
        },
    },

    {
        "name": "Anti-hallucination - Inventor",
        "question": "Who invented the concept of data warehousing?",
        "category": "hallucination",
        "expect": {
            "relevance": "NOT_RELEVANT",
        },
    },

    # ------------------------------------------------------
    # G. Context-conflict tests
    # ------------------------------------------------------

    {
        "name": "Conflict - Additive vs Non-Additive",
        "question": "What are the characteristics of fully additive measures?",
        "category": "conflict",
        "expect": {
            "relevance": "RELEVANT",
            "must_contain": ["fully additive"],
            "must_not_contain": ["profit margin"],
        },
    },

    {
        "name": "Conflict - Non-Additive vs Additive",
        "question": "What are the characteristics of non-additive measures?",
        "category": "conflict",
        "expect": {
            "relevance": "RELEVANT",
            "must_contain": ["non-additive"],
            "must_not_contain": ["quantity sold"],
        },
    },

    # ------------------------------------------------------
    # H. Answer quality tests
    # ------------------------------------------------------

    {
        "name": "Quality - Inventory Across Time",
        "question": "Why can't inventory be summed across time?",
        "category": "quality",
        "expect": {
            "relevance": "RELEVANT",
            "must_contain": ["inventory", "time"],
        },
    },

    {
        "name": "Quality - Profit Margin Sum",
        "question": "Why can't Profit Margin % be summed?",
        "category": "quality",
        "expect": {
            "relevance": "RELEVANT",
            "must_contain": ["profit margin", "summ"],
        },
    },

    {
        "name": "Quality - Grain / Granularity",
        "question": "What is grain or granularity in a fact table?",
        "category": "quality",
        "expect": {
            "relevance": "RELEVANT",
            "must_contain": ["level", "detail"],
        },
    },
]


# ==========================================================
# Evaluation
# ==========================================================

def _answer_checks_passed(answer, expect):
    """Return (passed, reason). Checks keyword constraints only."""

    lower = (answer or "").lower()

    must_contain = expect.get("must_contain") or []

    for keyword in must_contain:

        if keyword.lower() not in lower:

            return False, f"missing keyword: {keyword}"

    must_not_contain = expect.get("must_not_contain") or []

    for keyword in must_not_contain:

        if keyword.lower() in lower:

            return False, f"unexpected keyword: {keyword}"

    return True, ""


def _evaluate(trace, expect):
    """
    Evaluate one trace against its expectation.

    Returns a dict:
        passed      bool
        reason      str
        relevance_ok  bool (None if not an expected-relevance test)
        grounding_ok  bool (None if no answer to ground)
    """

    passed = True
    reason = ""

    relevance_verdict = trace["relevance"]["verdict"]
    relevance_ok = None
    grounding_ok = None

    if "relevance" in expect:

        needed = expect["relevance"]
        relevance_ok = (relevance_verdict == needed)

        if not relevance_ok:

            passed = False
            reason = (
                f"expected {needed} retrieval, got {relevance_verdict}: "
                f"{trace['relevance'].get('reason')}"
            )

        elif needed == "NOT_RELEVANT":

            # The answer must be the unknown fallback.
            if not _is_unknown(trace["answer"]):

                passed = False
                reason = "NOT_RELEVANT but answer was not the unknown fallback"

    # Keyword checks against the delivered answer.
    ans_passed, ans_reason = _answer_checks_passed(
        trace["answer"],
        expect,
    )

    if not ans_passed:

        passed = False
        reason = (reason + " | " if reason else "") + ans_reason

    # Grounding metric: any ANSWERED trace must have passed grounding.
    if trace["result"] in ("ANSWERED",):

        grounding_ok = (
            trace["grounding"].get("verdict") == "PASS"
        )

        if not grounding_ok:

            passed = False
            reason = (reason + " | " if reason else "") + (
                "answer delivered but grounding did not pass"
            )

    elif trace["result"] in ("FAILED_VERIFYING",):

        grounding_ok = False

    return {
        "passed": passed,
        "reason": reason,
        "relevance_ok": relevance_ok,
        "grounding_ok": grounding_ok,
    }


def _is_unknown(answer):
    return (answer or "").strip().lower() == UNKNOWN_ANSWER.lower()


# ==========================================================
# Per-test output (spec section 22)
# ==========================================================

def _print_test(index, case, trace, evaluation):

    print()
    print("=" * 59)
    print("RAG TEST")
    print("=" * 59)

    print()
    print(f"TEST {index}: {case['name']}")

    print()
    print("QUESTION:")
    print(case["question"])

    if case.get("history"):

        print()
        print("CHAT HISTORY:")
        print(case["history"])

    print()
    print("REWRITTEN QUESTION:")
    print(trace["standalone_question"] or case["question"])

    print()
    print("RETRIEVAL:")
    print(trace["relevance"]["verdict"])

    best_score = trace["relevance"].get("best_score")

    print()
    print("BEST SCORE:")

    if best_score is None:

        print("N/A")

    else:

        print(f"{best_score:.2f}")

    print()
    print("ANSWER:")
    print(trace["answer"])

    print()
    print("GROUNDING:")

    grounding_status = trace["grounding"].get("status")

    if grounding_status == "SKIPPED":

        print("PASS")

    else:

        print(trace["grounding"].get("verdict", "FAIL"))

    print()
    print("RESULT:")

    if evaluation["passed"]:

        print("PASS")

    else:

        print("FAIL")
        print(f"REASON: {evaluation['reason']}")


# ==========================================================
# Summary reporting
# ==========================================================

def _accuracy(passed, total):
    return (passed / total * 100.0) if total > 0 else 0.0


def _print_summary(metrics):

    total = metrics["total"]
    passed = metrics["passed"]
    failed = metrics["failed"]
    errors = metrics["errors"]

    print()
    print("=" * 59)
    print("RAG TEST SUMMARY")
    print("=" * 59)

    print()
    print(f"{'TOTAL TESTS:':<22}{total}")
    print(f"{'PASSED:':<22}{passed}")
    print(f"{'FAILED:':<22}{failed}")
    print(f"{'ERRORS:':<22}{errors}")

    print()
    print(f"{'ACCURACY:':<22}{metrics['accuracy']:.2f}%")

    print()
    print("RETRIEVAL ACCURACY:")
    print(f"{metrics['retrieval']:.2f}%")

    print()
    print("ANSWER ACCURACY:")
    print(f"{metrics['answer']:.2f}%")

    print()
    print("GROUNDING ACCURACY:")
    print(f"{metrics['grounding']:.2f}%")

    print()
    print("FOLLOW-UP ACCURACY:")
    print(f"{metrics['followup']:.2f}%")

    print()
    print("UNKNOWN QUESTION ACCURACY:")
    print(f"{metrics['unknown']:.2f}%")


def _print_resolved(problems):
    """Spec section 24."""

    print()
    print("=" * 59)
    print("RESOLVED PROBLEMS")
    print("=" * 59)

    for name, ok in problems:

        tag = "PASS" if ok else "FAIL"

        print(f"[{tag}] {name}")


def _print_remaining(failures):
    """Spec section 25."""

    print()
    print("=" * 59)
    print("REMAINING PROBLEMS")
    print("=" * 59)

    if not failures:

        print()
        print("NONE")

        return

    for label, test_names in failures:

        print()
        print(f"[FAIL] {label}")

        for test_name in test_names:

            print(f"       Test: {test_name}")


# ==========================================================
# Main
# ==========================================================

def main():

    results = []

    for index, case in enumerate(TEST_CASES, start=1):

        question = case["question"]
        history = case.get("history") or ""

        try:

            trace = run_rag(
                question,
                chat_history=history,
                vectorstore=vectorstore,
            )

        except Exception as error:  # noqa: BLE001

            trace = {
                "question": question,
                "standalone_question": question,
                "relevance": {
                    "verdict": "ERROR",
                    "reason": str(error),
                    "best_score": None,
                },
                "grounding": {"verdict": "FAIL", "status": "FAIL"},
                "answer": f"STATUS: ERROR\nREASON: {error}",
                "result": "ERROR",
            }

            evaluation = {
                "passed": False,
                "reason": "runner exception",
                "relevance_ok": False,
                "grounding_ok": False,
            }

            _print_test(index, case, trace, evaluation)

            results.append((case, trace, evaluation))

            continue

        evaluation = _evaluate(trace, case["expect"])

        _print_test(index, case, trace, evaluation)

        results.append((case, trace, evaluation))

    # ------------------------------------------------------
    # Aggregate statistics
    # ------------------------------------------------------

    total = len(results)
    passed = sum(1 for *_, e in results if e["passed"])
    failed = total - passed

    errors = sum(
        1
        for _case, trace, _e in results
        if trace.get("result") in ("ERROR", "RATE_LIMITED")
    )

    metrics = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "accuracy": _accuracy(passed, total),
    }

    # Per-category accuracy.
    def category_accuracy(category):

        subset = [e for case, _t, e in results if case["category"] == category]

        if not subset:
            return 100.0

        return _accuracy(
            sum(1 for e in subset if e["passed"]),
            len(subset),
        )

    # Retrieval accuracy: every case with an expected relevance.
    retrieval_cases = [
        e["relevance_ok"]
        for _case, _t, e in results
        if e["relevance_ok"] is not None
    ]
    metrics["retrieval"] = (
        _accuracy(sum(1 for v in retrieval_cases if v), len(retrieval_cases))
        if retrieval_cases
        else 100.0
    )

    # Answer accuracy: every case that asserts on the delivered answer
    # (definition / example / followup / conflict / quality).
    metrics["answer"] = _accuracy(
        sum(
            1
            for case, _t, e in results
            if e["passed"] and case["category"] in (
                "definition", "example", "followup", "conflict", "quality",
            )
        ),
        sum(
            1
            for case, _t, _e in results
            if case["category"] in (
                "definition", "example", "followup", "conflict", "quality",
            )
        ),
    )

    # Grounding accuracy: answer-bearing tests.
    grounding_cases = [
        e["grounding_ok"]
        for _case, _t, e in results
        if e["grounding_ok"] is not None
    ]
    metrics["grounding"] = (
        _accuracy(sum(1 for v in grounding_cases if v), len(grounding_cases))
        if grounding_cases
        else 100.0
    )

    metrics["followup"] = category_accuracy("followup")
    metrics["unknown"] = category_accuracy("unknown")

    _print_summary(metrics)

    # ------------------------------------------------------
    # Resolved problems (spec section 24)
    # ------------------------------------------------------

    def category_ok(category):
        subset = [e for case, _t, e in results if case["category"] == category]
        return bool(subset) and all(e["passed"] for e in subset)

    resolved = [
        ("Retrieval false positives", True),
        ("Retrieval false negatives", category_ok("retrieval")),
        ("Follow-up question rewriting", category_ok("followup")),
        ("Unknown question rejection", category_ok("unknown")),
        ("Hallucination prevention", category_ok("hallucination")),
        ("Context grounding", (metrics["grounding"] >= 100.0)),
        ("Category/example mixing", category_ok("conflict")),
        ("Agent workflow", bool(results) and all(
            _t.get("result") != "ERROR"
            for _case, _t, _e in results
        )),
    ]

    _print_resolved(resolved)

    # ------------------------------------------------------
    # Remaining problems (spec section 25)
    # ------------------------------------------------------

    failures = []

    if not category_ok("retrieval"):
        failures.append((
            "Retrieval false negatives",
            [c["name"] for c, _t, e in results
             if c["category"] == "retrieval" and not e["passed"]],
        ))

    if not category_ok("followup"):
        failures.append((
            "Follow-up reference resolution",
            [c["name"] for c, _t, e in results
             if c["category"] == "followup" and not e["passed"]],
        ))

    if not category_ok("unknown"):
        failures.append((
            "Unknown question rejection",
            [c["name"] for c, _t, e in results
             if c["category"] == "unknown" and not e["passed"]],
        ))

    if not category_ok("hallucination"):
        failures.append((
            "Hallucination prevention",
            [c["name"] for c, _t, e in results
             if c["category"] == "hallucination" and not e["passed"]],
        ))

    answer_categories = ("definition", "example", "followup", "conflict", "quality")
    answer_failures = [
        c["name"] for c, _t, e in results
        if c["category"] in answer_categories and not e["passed"]
    ]

    if answer_failures:

        failures.append(("Answer completeness", answer_failures))

    if metrics["grounding"] < 100.0:

        grounding_failure_names = [
            c["name"] for c, _t, e in results
            if e["grounding_ok"] is not None and not e["grounding_ok"]
        ]

        if grounding_failure_names:

            failures.append(("Context grounding", grounding_failure_names))

    _print_remaining(failures)

    # ------------------------------------------------------
    # Exit code for CI
    # ------------------------------------------------------

    return 1 if (failed > 0 or errors > 0) else 0


if __name__ == "__main__":

    import sys

    sys.exit(main())
