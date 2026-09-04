from langchain_huggingface import HuggingFaceEmbeddings


def create_embedding_model():
    embeddings = HuggingFaceEmbeddings(
        model_name="intfloat/e5-base-v2",
        encode_kwargs={"prompt": "passage: "},
        query_encode_kwargs={"prompt": "query: "},
    )

    return embeddings