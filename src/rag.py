from src.cromaDB import load_vectorstore
from src.embeddings import create_embedding_model
from src.agents.relevance import check_relevance_evidence
from src.agents.workflow import run_rag


# ==========================================================
# RAG entry points
#
# Heavy lifting is delegated to the agent modules:
#
#   run_rag()  -> the full Query Understanding -> Retrieval ->
#                 Relevance -> Answer Generation -> Grounding
#                 workflow (src/agents/workflow.py)
# ==========================================================

embeddings = create_embedding_model()

vectorstore = load_vectorstore(embeddings)


# ==========================================================
# Ask question (workflow wrapper)
#
# Backward-compatible tuple interface used by the test
# scripts:
#
#     answer, documents = ask_question(question, chat_history="")
# ==========================================================

def ask_question(question, chat_history=""):
    """
    Run the full agent workflow and return (answer, documents).

    On the final answer the retrieved documents are returned.
    On rejection / failure an empty document list is returned,
    matching the historic behaviour.
    """

    trace = run_rag(
        question,
        chat_history=chat_history,
        vectorstore=vectorstore,
    )

    if trace["result"] == "NOT_RELEVANT":
        return trace["answer"], []

    if trace["result"] == "ERROR":
        return trace["answer"], []

    documents = trace["retrieval"]["documents"]

    return trace["answer"], documents


# ==========================================================
# Check retrieval relevance (test shim)
#
# Used by test_retrieval_threshold.py:
#
#     is_relevant, best_score = check_retrieval_relevance(...)
# ==========================================================

def check_retrieval_relevance(question):
    """
    Multi-signal relevance check against the vectorstore.

    Returns:
        (is_relevant: bool, best_score: float | None)
    """

    verdict = check_relevance_evidence(
        vectorstore,
        question,
    )

    is_relevant = (
        verdict["verdict"] == "RELEVANT"
    )

    return is_relevant, verdict["best_score"]