def extract_response_text(response):
    """
    Extract plain text from an LLM response.

    Handles both plain strings and structured content lists.
    """

    if isinstance(response.content, list):

        texts = []

        for item in response.content:

            if isinstance(item, dict) and "text" in item:
                texts.append(item["text"])

        return "".join(texts)

    return response.content


def build_context(documents):
    """
    Build the CONTEXT block for the answer-generation prompt.

    Each document is prefixed with its 1-based page number
    when the page metadata is present.
    """

    context_parts = []

    for document in documents:

        page = document.metadata.get("page")

        if page is not None:

            page_number = page + 1

            context_parts.append(
                f"[PAGE {page_number}]\n"
                f"{document.page_content}"
            )

        else:

            context_parts.append(
                document.page_content
            )

    return "\n\n".join(context_parts)