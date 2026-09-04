# data/

This directory holds the **documents** that get embedded into the vector
stores. Compiled vector stores (`chroma_db/`, `chroma_db_subjects/`,
`*.sqlite3`, `data/vectorstore/`) are git-ignored; documents are committed so
the project is fully self-contained and a reviewer can build a store and chat
immediately.

## Demo corpus (committed & regenerable)

The bundled documents are original, self-contained study materials:

| File | Subject | Source |
|------|---------|--------|
| `Lecture 1 - 3 Introductory Lecture.pdf` | Data Warehousing | committed |
| `Lecture 4.pdf` | Data Warehousing | committed |
| `Lecture 5 Types of Dimensions.pdf` | Data Warehousing | committed |
| `Lecture - Machine Learning.pdf` | Machine Learning | generated |
| `Lecture - Computer Networks.pdf` | Computer Networks | generated |
| `Lecture - Database Systems.pdf` | Database Systems | generated |

The three `Lecture - *.pdf` subject lectures are synthetic and regenerable
(original text, no copyrighted material):

```
python scripts/make_synthetic_lectures.py   # writes data/Lecture - *.pdf
```

## Building the vector stores

```
python scripts/build_vectorstore.py --all    # builds chroma_db + chroma_db_subjects/*
```

This builds the primary **Data Warehousing** store (`./chroma_db`, the default
API collection) as well as the three cross-subject stores used to validate that
the agents stay subject-agnostic.

## Bring your own documents

This is a subject-agnostic RAG system. Drop your own PDFs in here (or use the
web UI's **Documents** manager to upload and process them) and they become a
new searchable library.
