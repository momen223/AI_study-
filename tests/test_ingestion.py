"""
Ingestion pipeline test.

Validates the PDF -> pages -> chunks -> embeddings path end to end using a
tiny synthetic PDF generated on the fly, so the test is self-contained and
needs no bundled data or machine-specific paths.

  python tests/test_ingestion.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fpdf import FPDF

from src.ingestion import load_pdf
from src.chunking import split_documents
from src.embeddings import create_embedding_model


def _make_pdf(path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=14)
    for i in range(3):
        pdf.cell(0, 10, f"This is explanatory line {i + 1} of a demo lecture.")
        pdf.ln()
    # A section break so chunking/splitting has something to work with.
    pdf.add_page()
    pdf.set_font("helvetica", size=14)
    for i in range(10):
        pdf.cell(0, 10, f"Detail paragraph content number {i + 1}.")
        pdf.ln()
    pdf.output(path)


def main():
    failures = 0

    def check(name, condition):
        nonlocal failures
        tag = "PASS" if condition else "FAIL"
        print(f"[{tag}] {name}")
        if not condition:
            failures += 1

    tmp = tempfile.mkdtemp(prefix="rag_ingest_")
    pdf_path = os.path.join(tmp, "demo_lecture.pdf")
    _make_pdf(pdf_path)

    # Phase 1: load PDF -> pages
    pages = load_pdf(pdf_path)
    print(f"Loaded {len(pages)} pages.")
    check("PDF loaded into pages", len(pages) >= 1 and pages[0].page_content)

    # Phase 2: split into chunks
    chunks = split_documents(pages)
    print(f"Created {len(chunks)} chunks.")
    check("Split produced chunks", len(chunks) >= 1)
    check("Chunks carry content", all(c.page_content for c in chunks))

    # Phase 3: embed the chunks (offline, sentence-transformers)
    embeddings = create_embedding_model()
    vectors = embeddings.embed_documents([c.page_content for c in chunks])
    print(f"Generated {len(vectors)} embeddings.")
    check("Embeddings match chunk count", len(vectors) == len(chunks))
    check("Embeddings have expected dimension",
          len(vectors) and len(vectors[0]) > 0)

    # Cleanup
    try:
        os.remove(pdf_path)
        os.rmdir(tmp)
    except OSError:
        pass

    print("=" * 60)
    print("RESULT:", "OK" if failures == 0 else f"{failures} FAILURES")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
