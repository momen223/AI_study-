# ==========================================================
# Library (collection) discovery + store helpers.
#
# A "library" wraps a Chroma vectorstore that the API can chat
# against. There is always a primary/default library (the Data
# Warehousing store in ./chroma_db) plus any per-subject stores
# (./chroma_db_subjects/*). Uploaded documents create additional
# dynamic libraries.
# ==========================================================

import os

from src.cromaDB import load_vectorstore
from src.embeddings import create_embedding_model

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
UPLOAD_INDEX = os.path.join(UPLOAD_DIR, "index.json")

# Subject stores built by scripts/build_vectorstore.py --all
SUBJECT_LIBRARIES = [
    {
        "id": "databases",
        "name": "Database Systems",
        "collection": "databases",
        "persist": "./chroma_db_subjects/databases",
    },
    {
        "id": "machine_learning",
        "name": "Machine Learning",
        "collection": "machine_learning",
        "persist": "./chroma_db_subjects/machine_learning",
    },
    {
        "id": "networks",
        "name": "Computer Networks",
        "collection": "networks",
        "persist": "./chroma_db_subjects/networks",
    },
]

_EMBEDDINGS = None
_STORE_CACHE = {}


def get_embeddings():
    global _EMBEDDINGS
    if _EMBEDDINGS is None:
        _EMBEDDINGS = create_embedding_model()
    return _EMBEDDINGS


def _store_exists(persist):
    return os.path.isdir(persist)


def list_libraries():
    """Return the libraries available to chat against."""
    from src.config import PERSIST_DIRECTORY, COLLECTION_NAME

    libs = [
        {
            "id": COLLECTION_NAME,
            "name": COLLECTION_NAME.replace("_", " ").title(),
            "collection": COLLECTION_NAME,
            "persist": PERSIST_DIRECTORY,
            "default": True,
            "available": _store_exists(PERSIST_DIRECTORY),
            "type": "primary",
        }
    ]

    for spec in SUBJECT_LIBRARIES:
        libs.append({
            **spec,
            "default": False,
            "available": _store_exists(spec["persist"]),
            "type": "subject",
        })

    # Dynamically uploaded libraries (from uploads/index.json).
    for entry in _read_upload_index():
        persist = os.path.join(BASE_DIR, "uploads", "stores",
                               entry["store_id"])
        libs.append({
            "id": entry["store_id"],
            "name": entry.get("title") or entry["store_id"],
            "collection": entry["store_id"],
            "persist": persist,
            "default": False,
            "available": _store_exists(persist),
            "type": "upload",
            "documents": entry.get("documents", []),
        })

    return libs


def get_library(library_id=None):
    """Return the (collection, persist) for a library id, or the default."""
    from src.config import PERSIST_DIRECTORY, COLLECTION_NAME
    if not library_id or library_id in (COLLECTION_NAME, "default", "primary"):
        return COLLECTION_NAME, PERSIST_DIRECTORY
    for lib in list_libraries():
        if lib["id"] == library_id:
            return lib["collection"], lib["persist"]
    return None, None


def load_store(collection, persist):
    """Load (and cache) a vectorstore for the given collection/persist."""
    key = (collection, persist)
    if key not in _STORE_CACHE:
        store = load_vectorstore(
            get_embeddings(),
            collection_name=collection,
            persist_directory=persist,
        )
        _STORE_CACHE[key] = store
    return _STORE_CACHE[key]


def reset_cache():
    _STORE_CACHE.clear()


# ==========================================================
# Uploaded-document index (JSON)
# ==========================================================

def _read_upload_index():
    if not os.path.exists(UPLOAD_INDEX):
        return []
    try:
        with open(UPLOAD_INDEX, "r", encoding="utf-8") as fh:
            data = __import__("json").load(fh)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_upload_index(entries):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with open(UPLOAD_INDEX, "w", encoding="utf-8") as fh:
        __import__("json").dump(entries, fh, indent=2)


def add_upload_entry(entry):
    entries = _read_upload_index()
    entries.append(entry)
    _write_upload_index(entries)


def list_uploads():
    return _read_upload_index()


def get_upload_entry(store_id):
    for e in _read_upload_index():
        if e["store_id"] == store_id:
            return e
    return None


def remove_upload_entry(store_id):
    entries = [e for e in _read_upload_index() if e["store_id"] != store_id]
    _write_upload_index(entries)


def ensure_dirs():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.join(UPLOAD_DIR, "files"), exist_ok=True)
    os.makedirs(os.path.join(UPLOAD_DIR, "stores"), exist_ok=True)
