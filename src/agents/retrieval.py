from src.config import (
    RETRIEVER_K,
    FETCH_K,
    MMR_LAMBDA,
)
from src.retriever import (
    create_retriever,
    similarity_search_with_scores,
)


# ==========================================================
# Retrieval Agent
#
# Retrieves the most useful document chunks.
#
# Primary strategy: MMR (diversified selection).
#   k        = number of documents to return
#   fetch_k  = number of candidates considered
#   lambda_mult = diversity / relevance trade-off
#
# All values remain configurable via src/config.py.
# ==========================================================


def retrieve(vectorstore, query, k=None, fetch_k=None, lambda_mult=None):
    """
    Retrieve documents for the query.

    Returns a dict:
        {
            "documents": list of Document,
            "metadata":  list of document metadata dicts,
            "pages":     list of page numbers (may contain None),
            "scores":    top-k similarity distances,
            "k":         number of documents requested,
            "query":     the query used,
        }

    NOTE: MMR performs a diversified selection, so the returned
    documents are NOT simply the top-k by similarity. The
    "scores" field is a companion signal giving the raw top-k
    similarities for the same query.
    """

    if k is None:
        k = RETRIEVER_K

    if fetch_k is None:
        fetch_k = FETCH_K

    if lambda_mult is None:
        lambda_mult = MMR_LAMBDA

    retriever = create_retriever(
        vectorstore,
        k=k,
        fetch_k=fetch_k,
        lambda_mult=lambda_mult,
    )

    documents = retriever.invoke(query)

    scored = similarity_search_with_scores(
        vectorstore,
        query,
        k=RETRIEVER_K,
    )

    scores = [
        score
        for _, score in scored
    ]

    metadata = [
        document.metadata
        for document in documents
    ]

    pages = [
        document.metadata.get("page")
        for document in documents
    ]

    return {
        "documents": documents,
        "metadata": metadata,
        "pages": pages,
        "scores": scores,
        "k": k,
        "query": query,
    }