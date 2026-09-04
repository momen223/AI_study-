from langchain_chroma import Chroma

from src.config import (
    PERSIST_DIRECTORY,
    COLLECTION_NAME,
)


# ==========================================================
# Vectorstore helpers
#
# `collection_name` / `persist_directory` default to the global
# config (the Data Warehousing corpus). They can be overridden by
# the generic multi-lecture harness to build/load one store per
# subject — the same production code, no per-subject logic.
# ==========================================================

def create_vectorstore(
    documents,
    embeddings,
    collection_name=None,
    persist_directory=None,
):
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        collection_name=collection_name or COLLECTION_NAME,
        persist_directory=persist_directory or PERSIST_DIRECTORY
    )

    return vectorstore


def load_vectorstore(
    embeddings,
    collection_name=None,
    persist_directory=None,
):
    vectorstore = Chroma(
        collection_name=collection_name or COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=persist_directory or PERSIST_DIRECTORY
    )

    return vectorstore