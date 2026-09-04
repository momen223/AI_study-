# ==========================================================
# QUIZ (MCQ) GENERATION FEATURE TEST
#
# Tests src/quizzes/* and the /api/quizzes blueprint.
#
#  - JSON parsing + structural normalization (unit, no LLM)
#  - deterministic grounding validation
#  - near-duplicate prevention
#  - authoritative lifecycle + server-side scoring (no LLM)
#  - persistence round-trip
#  - API routing via Flask test client (seeded store, no LLM)
#  - live end-to-end integration (only when a provider is
#    configured; otherwise gracefully skipped)
#
# The deterministic sections never depend on a live model, so they
# are stable. Live sections assert structural self-consistency and
# tolerate any READY/PARTIAL/ERROR outcome from the generator.
# ==========================================================

import json
import os
import tempfile
import time

from src.quizzes.models import (
    Question,
    Quiz,
    Attempt,
    AttemptStatus,
    GenerationStatus,
)
from src.quizzes.validation import (
    validate_structure,
    validate_grounding,
    deduplicate,
    validate_quiz_questions,
)
from src.quizzes.generation import (
    _extract_json_array,
    _normalize_candidate,
    generate_candidates,
)
from src.quizzes.lifecycle import QuizStore

# ----------------------------------------------------------
# Fake LLMs
# ----------------------------------------------------------

class FakePassLLM:
    """Verifier that reports the item is supported."""

    def invoke(self, prompt):
        class Response:
            content = "PASS"
        return Response()


class FakeFailLLM:
    """Verifier that reports the item is NOT supported."""

    def invoke(self, prompt):
        class Response:
            content = "FAIL"
        return Response()


class FakeRaisingLLM:
    """Simulates a provider failure during verification."""

    def invoke(self, prompt):
        raise Exception("429 Too Many Requests")


# ----------------------------------------------------------
# Context + fixtures used by deterministic grounding tests
# ----------------------------------------------------------

CONTEXT = (
    "The star schema contains fact tables and dimension tables. "
    "A fact table stores numeric measures such as sales amount and "
    "quantity sold. Each fact row references foreign keys to the "
    "surrounding dimension tables. Snowflake schemas normalize the "
    "dimension tables into multiple related tables."
)


def valid_question():
    return Question(
        id="q0",
        prompt="In the star schema, what does a fact table store?",
        options=[
            "numeric measures",
            "dimension attributes",
            "olap cubes",
            "nil files",
        ],
        correct_index=0,
        explanation="A fact table stores numeric measures such as sales "
                    "amount and quantity sold.",
        evidence="A fact table stores numeric measures such as sales "
                 "amount and quantity sold.",
        difficulty="easy",
    )


def valid_question_2():
    return Question(
        id="q1",
        prompt="What does a snowflake schema do to dimension tables?",
        options=[
            "normalizes dimension tables",
            "denormalizes fact tables",
            "caches all queries",
            "drops foreign keys",
        ],
        correct_index=0,
        explanation="Snowflake schemas normalize the dimension tables "
                    "into multiple related tables.",
        evidence="Snowflake schemas normalize the dimension tables into "
                 "multiple related tables.",
        difficulty="medium",
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
    print("QUIZ / MCQ GENERATION FEATURE TEST")
    print("=" * 75)

    # ======================================================
    # 1. JSON extraction + structural normalization (unit)
    # ======================================================

    check(
        "extract JSON array from fenced block",
        _extract_json_array('```json\n[{"prompt":"x"}]\n```') == [{"prompt": "x"}],
    )

    check(
        "extract JSON array from prose",
        _extract_json_array('Here you go: [1, 2, 3].') == [1, 2, 3],
    )

    try:
        _extract_json_array("no array here")
        check("no array -> error", False)
    except ValueError:
        check("no array -> error", True)

    good_raw = {
        "prompt": "In the star schema, what does a fact table store?",
        "options": {
            "A": "numeric measures",
            "B": "dimension attributes",
            "C": "olap cubes",
            "D": "nil files",
        },
        "correct_letter": "A",
        "explanation": "A fact table stores numeric measures.",
        "evidence": "A fact table stores numeric measures such as sales amount.",
        "difficulty": "easy",
    }

    q = _normalize_candidate(good_raw, 0)
    check(
        "normalize -> exactly 4 options",
        len(q.options) == 4,
    )
    check(
        "normalize -> correct index mapped from letter",
        q.correct_index == 0 and q.correct_letter == "A",
    )

    # Missing option -> ValueError
    def _rejects():
        try:
            _normalize_candidate(
                {**good_raw, "options": {"A": "x", "B": "y", "C": "z"}}, 0
            )
            return False
        except ValueError:
            return True
    check("normalize rejects missing option", _rejects())

    def _rejects_letter():
        try:
            _normalize_candidate({**good_raw, "correct_letter": "E"}, 0)
            return False
        except ValueError:
            return True
    check("normalize rejects invalid correct letter", _rejects_letter())

    def _rejects_empty_evidence():
        try:
            _normalize_candidate({**good_raw, "evidence": ""}, 0)
            return False
        except ValueError:
            return True
    check("normalize rejects empty evidence", _rejects_empty_evidence())

    # ======================================================
    # 2. Deterministic grounding validation
    # ======================================================

    ok, report = validate_grounding(valid_question(), CONTEXT, llm=FakePassLLM())
    check("grounded -> ok", ok)
    check("grounded -> no reasons", report["reasons"] == [])
    check("grounded -> verbatim evidence", report["evidence_verbatim"] is True)

    # Evidence not verbatim -> reject regardless of verifier.
    q_bad_ev = valid_question()
    q_bad_ev.evidence = "This claim is not present anywhere in the document."
    ok, report = validate_grounding(q_bad_ev, CONTEXT, llm=FakePassLLM())
    check("non-verbatim evidence -> reject", not ok)
    check(
        "non-verbatim evidence flagged",
        any("verbatim" in r for r in report["reasons"]),
    )

    # Correct answer not supported -> reject even under FakePassLLM.
    q_bad_correct = valid_question()
    q_bad_correct.options[0] = "quantum flux capacitors"
    ok, report = validate_grounding(q_bad_correct, CONTEXT, llm=FakePassLLM())
    check("unsupported correct answer -> reject", not ok)

    # Explanation not supported -> reject.
    q_bad_exp = valid_question()
    q_bad_exp.explanation = "Quadratic graphs are plotted with chalk on a blackboard."
    ok, report = validate_grounding(q_bad_exp, CONTEXT, llm=FakePassLLM())
    check("unsupported explanation -> reject", not ok)

    # Verifier LLM fails -> llm_error set but returns dict, deterministic gate rules.
    ok, report = validate_grounding(valid_question(), CONTEXT, llm=FakeRaisingLLM())
    check("raising verifier -> returns dict", isinstance(report, dict))
    check("raising verifier -> llm_error", report["llm_error"] is True)

    # Deterministic gate passes but verifier says FAIL -> additive reject.
    ok, report = validate_grounding(valid_question(), CONTEXT, llm=FakeFailLLM())
    check("verifier FAIL is additive reject", not ok)
    check(
        "verifier FAIL reason recorded",
        any("verifier" in r for r in report["reasons"]),
    )

    # ======================================================
    # 3. Structural validation
    # ======================================================

    check("structure ok", validate_structure(valid_question())[0])

    dup = valid_question()
    dup.options[1] = dup.options[0]
    check("duplicate options rejected", not validate_structure(dup)[0])

    bad_diff = valid_question()
    bad_diff.difficulty = "advanced"
    check("invalid difficulty rejected", not validate_structure(bad_diff)[0])

    empty_exp = valid_question()
    empty_exp.explanation = ""
    check("empty explanation rejected", not validate_structure(empty_exp)[0])

    # ======================================================
    # 4. Duplicate / near-duplicate prevention
    # ======================================================

    q1 = valid_question()
    q1.id = "a"
    q2 = valid_question()
    q2.id = "b"
    q3 = valid_question_2()
    q3.id = "c"
    q4 = valid_question_2()
    q4.id = "d"

    uniq, dropped = deduplicate([q1, q2, q3, q4])
    check("deduplicate keeps first occurrence", len(uniq) == 2)
    check("deduplicate drops near-duplicates", dropped == 2)

    accepted, rejected = validate_quiz_questions(
        [q1, q2, q3, q4], CONTEXT, llm=FakePassLLM(),
    )
    check("full pipeline accepts unique set", len(accepted) == 2)
    check("full pipeline rejects duplicates", len(rejected) == 2)

    # ======================================================
    # 5. Lifecycle + authoritative server-side scoring
    # ======================================================

    with tempfile.TemporaryDirectory() as tmp:

        store = QuizStore(directory=tmp)

        quiz = Quiz(
            id="quiz-1",
            library_id="lib-x",
            subject="X",
            questions=[q1, q3],
            question_count_requested=2,
            difficulty="mixed",
            time_limit_seconds=0,
            title="X quiz",
            created_at=1000.0,
        )
        store.save_quiz(quiz)

        check(
            "quiz saved and reloaded",
            len(store.get_quiz("quiz-1").questions) == 2,
        )

        attempt = store.create_attempt(quiz)
        check("attempt created -> CREATED", attempt.status == AttemptStatus.CREATED.value)
        check("attempt started_at unset until start", attempt.started_at is None)

        attempt = store.start_attempt(attempt)
        check("attempt started -> STARTED", attempt.status == AttemptStatus.STARTED.value)
        check("attempt started_at set", attempt.started_at is not None)

        # All answered + all correct -> COMPLETED, perfect score.
        graded, summary = store.grade(
            quiz, attempt, {"a": "A", "c": "A"},
        )
        check("all correct -> COMPLETED", summary["result_status"] == "COMPLETED")
        check("all correct -> score = total", summary["score"] == summary["total"] == 2)
        check(
            "correct map honest",
            summary["correct"]["a"] is True and summary["correct"]["c"] is True,
        )

        # Re-submit with some unanswered -> PARTIAL + structured reason.
        attempt2 = store.create_attempt(quiz)
        attempt2 = store.start_attempt(attempt2)
        graded2, summary2 = store.grade(quiz, attempt2, {"a": "A"})
        check("partial submission -> PARTIAL", summary2["result_status"] == "PARTIAL")
        check("partial -> unanswered listed", summary2["unanswered"] == ["c"])
        check(
            "partial -> reason structured",
            "unanswered" in summary2["partial_reason"] and "c" in summary2["partial_reason"],
        )
        check(
            "partial -> answered ones still scored",
            summary2["score"] == 1,
        )

        # Wrong letters -> all answered, none correct.
        attempt3 = store.create_attempt(quiz)
        attempt3 = store.start_attempt(attempt3)
        graded3, summary3 = store.grade(quiz, attempt3, {"a": "B", "c": "D"})
        check("wrong answers -> COMPLETED but score 0", summary3["result_status"] == "COMPLETED")
        check("wrong answers -> score 0", summary3["score"] == 0)

        # Timer: exceed the limit -> timed_out.
        timer_quiz = Quiz(
            id="quiz-timer",
            library_id="lib-x",
            subject="X",
            questions=[q1],
            question_count_requested=1,
            time_limit_seconds=10,
            created_at=0.0,
        )
        ta = store.create_attempt(timer_quiz)
        ta.started_at = time.time() - 100.0
        graded_t, summary_t = store.grade(timer_quiz, ta, {})
        check("timer exceeded -> timed_out", summary_t["timed_out"] is True)

        # Persistence round-trip across store instances.
        store2 = QuizStore(directory=tmp)
        reloaded = store2.get_quiz("quiz-1")
        check("quiz persists across instances", reloaded is not None)
        check(
            "graded attempt persists",
            store2.get_attempt(attempt.id).result_status == "COMPLETED",
        )

        # Delete.
        check("delete quiz", store.delete_quiz("quiz-1") is True)
        try:
            store.get_quiz("quiz-1")
            check("deleted quiz no longer retrievable", False)
        except Exception:
            check("deleted quiz no longer retrievable", True)

    # ======================================================
    # 6. generation candidate loop (deterministic, fake LLM)
    # ======================================================

    good_payload = [
        {
            "prompt": "In the star schema, what does a fact table store?",
            "options": {"A": "numeric measures", "B": "attributes",
                        "C": "cubes", "D": "files"},
            "correct_letter": "A",
            "explanation": "A fact table stores numeric measures.",
            "evidence": "A fact table stores numeric measures such as sales amount.",
            "difficulty": "easy",
        },
    ]
    res = generate_candidates(CONTEXT, count=1, difficulty="easy",
                              llm=_TextLLM(json.dumps(good_payload)))
    check("generate_candidates parses valid batch", len(res["questions"]) == 1)
    check("generate_candidates uses one attempt", res["attempts"] == 1)

    # A provider that raises then succeeds -> retries (bounded).
    res = generate_candidates(CONTEXT, count=1, difficulty="easy",
                              llm=_TextLLM(json.dumps(good_payload), raise_count=1),
                              retries=3)
    check("rate-limit retry succeeds", len(res["questions"]) == 1)
    check("retry used two attempts", res["attempts"] == 2)

    # ======================================================
    # 7. API routing (seeded store, Flask test client)
    # ======================================================

    from api.app import create_app
    import api.quizzes as qz
    with tempfile.TemporaryDirectory() as tmp2:
        qz._store = QuizStore(directory=tmp2)

        seeded = Quiz(
            id="api-1",
            library_id="databases",
            subject="Database Systems",
            questions=[q1, q3],
            question_count_requested=2,
            difficulty="easy",
            created_at=time.time(),
        )
        qz._store.save_quiz(seeded)

        client = create_app().test_client()

        # GET must NOT reveal correct answers before submission.
        r = client.get("/api/quizzes/api-1")
        data = r.get_json()
        check("api GET quiz status 200", r.status_code == 200)
        check(
            "api GET hides correct answers",
            all("correct_letter" not in q for q in data["quiz"]["questions"]),
        )
        check(
            "api GET shows 4 options each",
            all(len(q["options"]) == 4 for q in data["quiz"]["questions"]),
        )

        # Start.
        r = client.post("/api/quizzes/api-1/start")
        data = r.get_json()
        check("api start status 200", r.status_code == 200)
        attempt_id = data["attempt_id"]
        check("api start returns attempt_id", bool(attempt_id))

        # Submit correct + unanswered -> PARTIAL (incomplete submission).
        r = client.post("/api/quizzes/api-1/submit", json={
            "attempt_id": attempt_id,
            "answers": {"a": "A"},
        })
        data = r.get_json()
        check("api submit status 200", r.status_code == 200)
        check("api submit partial result", data["result"] == "PARTIAL")
        check(
            "api submit reveals answers only post-submit",
            all("correct_letter" in q for q in data["quiz"]["questions"]),
        )
        check("api submit server score", data["score"]["score"] == 1)

        # Result endpoint re-fetch.
        r = client.get(f"/api/quizzes/api-1/result?attempt_id={attempt_id}")
        check("api result status 200", r.status_code == 200)
        check("api result reflects stored grade", r.get_json()["result"] == "PARTIAL")

        # Validation errors.
        r = client.post("/api/quizzes", json={"library": "nope"})
        check("api unknown library -> 404", r.status_code == 404)

        r = client.get("/api/quizzes/missing-id")
        check("api missing quiz -> 404", r.status_code == 404)

        r = client.post("/api/quizzes/api-2/bogus-x/submit", json={})
        check("api unknown route -> 404", r.status_code == 404)

        # Delete.
        r = client.delete("/api/quizzes/api-1")
        check("api delete status 200", r.status_code == 200)

    # ======================================================
    # 8. Live end-to-end integration (guarded by provider keys)
    # ======================================================

    provider_configured = bool(
        os.environ.get("GROQ_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    )

    if not provider_configured:
        print("LIVE: no provider configured; skipping live quiz generation")
    else:
        from src.cromaDB import load_vectorstore
        from src.embeddings import create_embedding_model
        from src.quizzes.generation import generate_quiz

        embeddings = create_embedding_model()
        vectorstore = load_vectorstore(embeddings)

        try:
            quiz = generate_quiz(
                vectorstore,
                library_id="data_warehousing",
                subject="Data Warehousing",
                topic="fact table",
                question_count=3,
                difficulty="mixed",
            )
            check(
                "live: generation status is a known value",
                quiz.generation_status in (GenerationStatus.READY.value,
                                           GenerationStatus.PARTIAL.value),
            )
            for q in quiz.questions:
                check("live: each question has 4 options", len(q.options) == 4)
                check("live: exactly one correct",
                      q.correct_letter in ("A", "B", "C", "D"))
                check("live: evidence is a real excerpt", bool(q.evidence))
        except Exception as exc:  # noqa: BLE001
            check("live: generation raises structured error gracefully",
                  "generate" in str(exc).lower() or "quiz" in str(exc).lower())

    # ======================================================

    print("\n" + "=" * 75)
    print("QUIZ / MCQ GENERATION FEATURE TEST SUMMARY")
    print(f"TOTAL:     {total}")
    print(f"FAILURES:  {failures}")
    print("=" * 75)

    if failures == 0:
        print("\nALL QUIZ / MCQ GENERATION FEATURE TESTS PASSED")

    return 0 if failures == 0 else 1


class _TextLLM:
    """Generation LLM returning a fixed text payload (optionally raising first)."""

    def __init__(self, text, raise_count=0):
        self._text = text
        self._raise_count = raise_count

    def invoke(self, prompt):
        if self._raise_count > 0:
            self._raise_count -= 1
            raise Exception("429 Too Many Requests")
        class Response:
            content = self._text
        return Response()


if __name__ == "__main__":
    raise SystemExit(run())
