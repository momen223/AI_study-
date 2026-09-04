from src.config import (
    RETRIEVER_K,
    FETCH_K,
    MMR_LAMBDA,
)
from src.agents.query_understanding import understand_query
from src.agents.retrieval import retrieve
from src.agents.relevance import check_relevance_evidence
from src.agents.answer_generation import (
    generate_answer,
    UNKNOWN_ANSWER,
)
from src.agents.grounding import verify_grounding


# ==========================================================
# RAG Agent Workflow
#
# Orchestrates the full pipeline:
#
#   User Question
#        |
#        v
#   Query Understanding Agent
#        |
#        v
#   Retrieval Agent
#        |
#        v
#   Relevance / Evidence Agent
#        |
#        +---- Not relevant ----+ Unknown response
#        |
#        v
#   Answer Generation Agent
#        |
#        v
#   Grounding / Verification Agent
#        |
#        v
#   Final Answer
#
# The workflow never returns ungrounded content: a PASS verdict
# is required for an answer to be delivered. On FAIL the answer
# is regenerated once with the grounding reasons fed back as
# revision guidance; only a second PASS is accepted. If the
# corrected answer still fails, the safest generic behaviour is
# the UNKNOWN fallback.
#
# Result codes:
#   ANSWERED           answer passed grounding and is returned
#   UNKNOWN            answer agent said it cannot answer
#   NOT_RELEVANT       relevance agent rejected the question
#   FAILED_VERIFYING   answer failed the grounding checks
#   RATE_LIMITED       an LLM call failed (per spec: STATUS/REASON)
#   ERROR              unexpected workflow failure
# ==========================================================


def _unknown_trace(result, reason, **extra):
    """Build a minimal trace for terminal failure paths."""

    trace = {
        "question": "",
        "standalone_question": "",
        "intent": None,
        "detected_references": [],
        "rewrote": False,
        "query_error": False,
        "retrieval": {
            "documents": [],
            "metadata": [],
            "pages": [],
            "scores": [],
            "k": None,
            "query": "",
        },
        "relevance": {
            "verdict": "NOT_RELEVANT",
            "reason": reason,
            "best_score": None,
            "strong_count": 0,
            "relevant_count": 0,
            "scores": [],
            "overlap": {},
        },
        "generation": {
            "answer": "",
            "status": None,
            "reason": reason,
            "doc_count": 0,
        },
        "grounding": {
            "verdict": "FAIL",
            "status": "FAIL",
            "reasons": [],
            "checks": {},
            "llm_error": False,
        },
        "answer": UNKNOWN_ANSWER,
        "result": result,
        "error": reason,
    }

    trace.update(extra)

    return trace


def run_rag(
    question,
    chat_history="",
    vectorstore=None,
    k=None,
    fetch_k=None,
    lambda_mult=None,
):
    """
    Run the full agent workflow for one question.

    Returns a trace dict containing every stage's diagnostics
    plus the final `answer` and a `result` code.

    `vectorstore` must be provided (or the workflow cannot
    retrieve). `k` / `fetch_k` / `lambda_mult` override the
    config defaults when given.
    """

    if vectorstore is None:
        return _unknown_trace(
            "ERROR",
            "no vectorstore provided",
        )

    original = str(question or "").strip()

    # --------------------------------------------------
    # Step 1: Query Understanding
    # --------------------------------------------------

    try:

        understanding = understand_query(
            original,
            chat_history,
        )

    except Exception as exc:  # noqa: BLE001
        # Rewriting is best-effort. On LLM failure keep the
        # original question and continue with a note.
        understanding = {
            "standalone_question": original,
            "intent": None,
            "detected_references": [],
            "rewrote": False,
            "history_used": bool(
                chat_history and chat_history.strip()
            ),
        }
        query_error = True

    else:

        query_error = False

    standalone_question = understanding["standalone_question"]

    # --------------------------------------------------
    # Step 2: Retrieval
    # --------------------------------------------------

    try:

        retrieval = retrieve(
            vectorstore,
            standalone_question,
            k=k,
            fetch_k=fetch_k,
            lambda_mult=lambda_mult,
        )

    except Exception as exc:  # noqa: BLE001
        return _unknown_trace(
            "ERROR",
            f"retrieval failed: {exc}",
            question=original,
            standalone_question=standalone_question,
            intent=understanding["intent"],
            detected_references=understanding["detected_references"],
            rewrote=understanding["rewrote"],
            query_error=query_error,
        )

    documents = retrieval["documents"]

    # --------------------------------------------------
    # Step 3: Relevance / Evidence
    # --------------------------------------------------

    try:

        relevance = check_relevance_evidence(
            vectorstore,
            standalone_question,
            documents=documents,
        )

    except Exception as exc:  # noqa: BLE001
        return _unknown_trace(
            "ERROR",
            f"relevance check failed: {exc}",
            question=original,
            standalone_question=standalone_question,
            intent=understanding["intent"],
            detected_references=understanding["detected_references"],
            rewrote=understanding["rewrote"],
            query_error=query_error,
            retrieval=retrieval,
        )

    if relevance["verdict"] == "NOT_RELEVANT":

        return {
            "question": original,
            "standalone_question": standalone_question,
            "intent": understanding["intent"],
            "detected_references": understanding["detected_references"],
            "rewrote": understanding["rewrote"],
            "query_error": query_error,
            "retrieval": retrieval,
            "relevance": relevance,
            "generation": {
                "answer": UNKNOWN_ANSWER,
                "status": "UNKNOWN",
                "reason": "relevance rejected",
                "doc_count": len(documents),
            },
            "grounding": {
                "verdict": "PASS",
                "status": "SKIPPED",
                "reasons": ["unknown answer: nothing to verify"],
                "checks": {},
                "llm_error": False,
            },
            "answer": UNKNOWN_ANSWER,
            "result": "NOT_RELEVANT",
            "error": None,
        }

    # --------------------------------------------------
    # Step 4: Answer Generation
    # --------------------------------------------------

    generation = generate_answer(
        original,
        documents,
        rewritten_question=standalone_question,
    )

    if generation["status"] == "ERROR":

        return {
            "question": original,
            "standalone_question": standalone_question,
            "intent": understanding["intent"],
            "detected_references": understanding["detected_references"],
            "rewrote": understanding["rewrote"],
            "query_error": query_error,
            "retrieval": retrieval,
            "relevance": relevance,
            "generation": generation,
            "grounding": {
                "verdict": "FAIL",
                "status": "FAIL",
                "reasons": ["llm generation failed"],
                "checks": {},
                "llm_error": True,
            },
            "answer": "STATUS: ERROR\nREASON: "
                + (generation.get("reason") or "LLM rate limit"),
            "result": "RATE_LIMITED",
            "error": generation.get("reason"),
        }

    if generation["status"] == "UNKNOWN":

        # --------------------------------------------------
        # Anti-hallucination safety gate for revisions: the
        # generator has already forbidden the UNKNOWN answer.
        # If retrieval judged the context RELEVANT, the
        # conservative UNKNOWN is likely a spurious refusal
        # (model nondeterminism) rather than missing context.
        # Give the generator one corrective pass so it scans
        # the whole context before giving up. This keeps the
        # refusal be the answer's safety but retries the
        # answer on on-topic context. Only if the retry also
        # refuses do we fall through to UNKNOWN.
        # --------------------------------------------------

        if relevance.get("verdict") == "RELEVANT":

            feedback = (
                "Retrieval determined the provided CONTEXT IS on-topic and "
                "relevant to the question. Scan every CONTEXT section and "
                "extract/answer directly from the document. Do NOT return "
                "the 'I don't know' response unless literally none of the "
                "CONTEXT content addresses the question."
            )

            repaired = generate_answer(
                original,
                documents,
                rewritten_question=standalone_question,
                feedback=feedback,
            )

            if repaired["status"] == "OK":

                # Fall through to normal grounding/verification of the
                # recovered answer instead of returning UNKNOWN.
                generation = repaired

            else:

                return {
                    "question": original,
                    "standalone_question": standalone_question,
                    "intent": understanding["intent"],
                    "detected_references": understanding["detected_references"],
                    "rewrote": understanding["rewrote"],
                    "query_error": query_error,
                    "retrieval": retrieval,
                    "relevance": relevance,
                    "generation": repaired,
                    "grounding": {
                        "verdict": "PASS",
                        "status": "SKIPPED",
                        "reasons": ["unknown answer: nothing to verify"],
                        "checks": {},
                        "llm_error": False,
                    },
                    "answer": UNKNOWN_ANSWER,
                    "result": "UNKNOWN",
                    "error": repaired.get("reason"),
                }

        else:

            return {
                "question": original,
                "standalone_question": standalone_question,
                "intent": understanding["intent"],
                "detected_references": understanding["detected_references"],
                "rewrote": understanding["rewrote"],
                "query_error": query_error,
                "retrieval": retrieval,
                "relevance": relevance,
                "generation": generation,
                "grounding": {
                    "verdict": "PASS",
                    "status": "SKIPPED",
                    "reasons": ["unknown answer: nothing to verify"],
                    "checks": {},
                    "llm_error": False,
                },
                "answer": UNKNOWN_ANSWER,
                "result": "UNKNOWN",
                "error": generation.get("reason"),
            }

    answer = generation["answer"]

    # --------------------------------------------------
    # Step 5: Grounding / Verification
    # --------------------------------------------------

    grounding = verify_grounding(
        original,
        answer,
        documents,
        rewritten_question=standalone_question,
    )

    if grounding["verdict"] == "FAIL":

        # --------------------------------------------------
        # Corrective attempt: give the grounding reasons back
        # to the generator once so it can drop unsupported
        # claims. Only a second PASS is accepted.
        # --------------------------------------------------

        feedback = "\n".join(grounding["reasons"]) or None

        corrected = generate_answer(
            original,
            documents,
            rewritten_question=standalone_question,
            feedback=feedback,
        )

        if corrected["status"] == "ERROR":

            return {
                "question": original,
                "standalone_question": standalone_question,
                "intent": understanding["intent"],
                "detected_references": understanding["detected_references"],
                "rewrote": understanding["rewrote"],
                "query_error": query_error,
                "retrieval": retrieval,
                "relevance": relevance,
                "generation": corrected,
                "grounding": {
                    "verdict": "FAIL",
                    "status": "FAIL",
                    "reasons": ["llm generation failed"],
                    "checks": {},
                    "llm_error": True,
                },
"answer": "STATUS: ERROR\nREASON: "
            + (generation.get("reason") or "LLM rate limit"),
                "result": "RATE_LIMITED",
                "error": corrected.get("reason"),
            }

        if corrected["status"] == "UNKNOWN":

            return {
                "question": original,
                "standalone_question": standalone_question,
                "intent": understanding["intent"],
                "detected_references": understanding["detected_references"],
                "rewrote": understanding["rewrote"],
                "query_error": query_error,
                "retrieval": retrieval,
                "relevance": relevance,
                "generation": corrected,
                "grounding": {
                    "verdict": "PASS",
                    "status": "SKIPPED",
                    "reasons": ["unknown answer: nothing to verify"],
                    "checks": {},
                    "llm_error": False,
                },
                "answer": UNKNOWN_ANSWER,
                "result": "UNKNOWN",
                "error": corrected.get("reason"),
            }

        recheck = verify_grounding(
            original,
            corrected["answer"],
            documents,
            rewritten_question=standalone_question,
        )

        if recheck["verdict"] == "PASS":

            return {
                "question": original,
                "standalone_question": standalone_question,
                "intent": understanding["intent"],
                "detected_references": understanding["detected_references"],
                "rewrote": understanding["rewrote"],
                "query_error": query_error,
                "retrieval": retrieval,
                "relevance": relevance,
                "generation": corrected,
                "grounding": recheck,
                "answer": corrected["answer"],
                "result": "ANSWERED",
                "error": None,
            }

        return {
            "question": original,
            "standalone_question": standalone_question,
            "intent": understanding["intent"],
            "detected_references": understanding["detected_references"],
            "rewrote": understanding["rewrote"],
            "query_error": query_error,
            "retrieval": retrieval,
            "relevance": relevance,
            "generation": corrected,
            "grounding": recheck,
            "answer": UNKNOWN_ANSWER,
            "result": "FAILED_VERIFYING",
            "error": None,
        }

    return {
        "question": original,
        "standalone_question": standalone_question,
        "intent": understanding["intent"],
        "detected_references": understanding["detected_references"],
        "rewrote": understanding["rewrote"],
        "query_error": query_error,
        "retrieval": retrieval,
        "relevance": relevance,
        "generation": generation,
        "grounding": grounding,
        "answer": answer,
        "result": "ANSWERED",
        "error": None,
    }