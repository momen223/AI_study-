from src.config import (
    RETRIEVER_K,
    FETCH_K,
    MMR_LAMBDA,
)


def create_retriever(vectorstore, k=None, fetch_k=None, lambda_mult=None):
    """
    Create the main MMR retriever used by the RAG pipeline.

    All values default to the config constants but can be
    overridden per call.
    """

    if k is None:
        k = RETRIEVER_K

    if fetch_k is None:
        fetch_k = FETCH_K

    if lambda_mult is None:
        lambda_mult = MMR_LAMBDA

    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": k,
            "fetch_k": fetch_k,
            "lambda_mult": lambda_mult,
        },
    )

    return retriever


def similarity_search_with_scores(vectorstore, query, k=5):
    """
    Return documents together with their similarity scores.

    Chroma returns distance scores:
        LOWER = MORE SIMILAR
        HIGHER = LESS SIMILAR

    This function is used for retrieval evaluation
    and relevance checking.

    It does NOT replace the main MMR retriever.
    """

    results = vectorstore.similarity_search_with_score(
        query,
        k=k,
    )

    return results