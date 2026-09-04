"""
Build one Chroma vectorstore per subject lecture.

Purely a harness/utility step for the generic multi-lecture validation
(FINAL_REMAINING_WORK Tasks 3 & 4). It drives the SAME production ingestion
and vectorstore code used by the Data Warehousing corpus, just pointed at a
per-subject collection and persist directory. It adds no per-subject logic
to any agent or prompt.

Usage:
    python scripts/build_vectorstore.py <subject>
      or, to build every configured subject:
    python scripts/build_vectorstore.py --all

Configuring a subject:
    SUBJECTS[<name>] = {
        "pdfs": [relative paths under data/],
        "collection": collection name,
        "persist": persist directory,
    }

The Data Warehousing subject already has a persisted store (created by the
original ingestion flow) at ./chroma_db with collection data_warehousing. For
consistency it is re-built here into the same location when requested.
"""

import os
import shutil
import sys

# Allow `python scripts/build_vectorstore.py` to import the src package.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ingestion import load_pdf
from src.chunking import split_documents
from src.embeddings import create_embedding_model
from src.cromaDB import create_vectorstore

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


SUBJECTS = {
    "data_warehousing": {
        "pdfs": [
            "Lecture 1 - 3 Introductory Lecture.pdf",
            "Lecture 4.pdf",
            "Lecture 5 Types of Dimensions.pdf",
        ],
        "collection": "data_warehousing",
        "persist": "./chroma_db",
    },
    "databases": {
        "pdfs": ["Lecture - Database Systems.pdf"],
        "collection": "databases",
        "persist": "./chroma_db_subjects/databases",
    },
    "networks": {
        "pdfs": ["Lecture - Computer Networks.pdf"],
        "collection": "networks",
        "persist": "./chroma_db_subjects/networks",
    },
    "machine_learning": {
        "pdfs": ["Lecture - Machine Learning.pdf"],
        "collection": "machine_learning",
        "persist": "./chroma_db_subjects/machine_learning",
    },
}


def build_subject(name, cfg):
    embeddings = create_embedding_model()

    # Rebuild cleanly: Chroma.from_documents APPENDS to an existing
    # collection, so wipe the persist dir first to avoid stale-duplicate
    # chunks when a corpus is regenerated.
    if os.path.isdir(cfg["persist"]):
        shutil.rmtree(cfg["persist"])

    all_pages = []
    for rel in cfg["pdfs"]:
        path = os.path.join(DATA_DIR, rel)
        print(f"  loading {rel}")
        all_pages.extend(load_pdf(path))

    chunks = split_documents(all_pages)
    print(f"  {len(chunks)} chunks")

    vs = create_vectorstore(
        chunks,
        embeddings,
        collection_name=cfg["collection"],
        persist_directory=cfg["persist"],
    )
    print(f"  built store collection='{cfg['collection']}' persist='{cfg['persist']}'")
    return vs


def main():
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        names = list(SUBJECTS.keys())
        print("Available subjects:", ", ".join(names))
        return

    if "--all" in args:
        names = list(SUBJECTS.keys())
    else:
        names = [a for a in args if a in SUBJECTS]

    if not names:
        print("No valid subject given. Available:", ", ".join(SUBJECTS.keys()))
        return

    for name in names:
        print(f"Building subject '{name}' ...")
        build_subject(name, SUBJECTS[name])
        print(f"  done '{name}'")


if __name__ == "__main__":
    main()
