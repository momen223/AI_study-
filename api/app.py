# ==========================================================
# Flask REST API for the Agentic RAG system.
#
#   POST /api/chat                  ask a question against a library
#   GET  /api/libraries             list available collections
#   POST /api/documents/upload      upload a PDF (to be processed)
#   POST /api/documents/process     embed an uploaded PDF into a library
#   GET  /api/documents             list uploads + ingest status
#   DELETE /api/documents/<id>      remove an uploaded document/library
#   GET  /api/health                readiness probe
#
# The API deliberately exposes only *safe structured metadata* from the
# workflow trace (intent, rewritten question, relevance verdict, grounding
# verdict, retrieved citations, scores). It never leaks raw chain-of-thought
# and never returns ungrounded content.
# ==========================================================

import sys
import json
import os
import time
import uuid

# Ensure the project root is importable regardless of how this module is
# launched (`python api/app.py`, `python -m api.app`, or via a launcher).
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SRC_DIR, os.pardir))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from flask import Flask, jsonify, request
from flask_cors import CORS

from src.agents.workflow import run_rag
from src.agents.answer_generation import UNKNOWN_ANSWER
from api import libraries as libs
from api.quizzes import quiz_bp


RESULT_OK = {"ANSWERED"}
RESULT_UNKNOWN = {"UNKNOWN", "NOT_RELEVANT"}
RESULT_ERROR = {"ERROR", "RATE_LIMITED", "FAILED_VERIFYING"}


def create_app():
    app = Flask(__name__)
    CORS(app)
    app.register_blueprint(quiz_bp)

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------

    def _clean_source(source):
        """Return a portable filename for a citation source.

        The retriever stores the absolute PDF path in document metadata.
        Exposing that leaks machine-specific paths (e.g. C:\\Users\\...), so
        we surface only the basename in the API output.
        """
        if not source:
            return "document"
        return os.path.basename(str(source))

    def _citation(source, page, score, snippet):
        return {
            "source": _clean_source(source),
            "page": page,
            "score": score,
            "snippet": snippet,
        }

    def _safe_citations(trace):
        citations = []
        retrieval = trace.get("retrieval") or {}
        documents = retrieval.get("documents") or []
        metadata = retrieval.get("metadata") or []
        pages = retrieval.get("pages") or []
        scores = retrieval.get("scores") or []
        seen = set()
        for i, doc in enumerate(documents):
            meta = metadata[i] if i < len(metadata) else (doc.metadata or {})
            page = pages[i] if i < len(pages) else meta.get("page")
            score = scores[i] if i < len(scores) else None
            source = meta.get("source") or "document"
            key = (source, page)
            if key in seen:
                continue
            seen.add(key)
            content = getattr(doc, "page_content", "") or ""
            citations.append(_citation(
                source=source,
                page=page,
                score=score,
                snippet=content[:600],
            ))
        return citations

    def _trace_response(trace, started):
        processing_ms = int((time.time() - started) * 1000)
        result = trace.get("result", "ERROR")

        citations = _safe_citations(trace)

        response = {
            "answer": trace.get("answer") or "",
            "result": result,
            "error": trace.get("error"),
            "standalone_question": trace.get("standalone_question"),
            "intent": trace.get("intent"),
            "rewrote": bool(trace.get("rewrote")),
            "query_error": bool(trace.get("query_error")),
            "relevance": {
                "verdict": (trace.get("relevance") or {}).get("verdict"),
                "reason": (trace.get("relevance") or {}).get("reason"),
                "best_score": (trace.get("relevance") or {}).get("best_score"),
                "strong_count": (trace.get("relevance") or {}).get("strong_count"),
                "relevant_count": (trace.get("relevance") or {}).get("relevant_count"),
            },
            "grounding": {
                "verdict": (trace.get("grounding") or {}).get("verdict"),
                "status": (trace.get("grounding") or {}).get("status"),
            },
            "citations": citations,
            "sources": [c["source"] for c in citations],
            "processing_ms": processing_ms,
            "is_unknown": (trace.get("answer") or "").strip().lower()
                == UNKNOWN_ANSWER.lower(),
        }
        return response

    def _load_for_id(library_id):
        collection, persist = libs.get_library(library_id)
        if not collection:
            return None, None, "unknown library"
        try:
            store = libs.load_store(collection, persist)
        except Exception as exc:  # noqa: BLE001
            return None, None, f"failed to load library: {exc}"
        return store, collection, None

    # --------------------------------------------------
    # Health
    # --------------------------------------------------

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "ok",
            "service": "agentic-rag-api",
            "time": time.time(),
        })

    # --------------------------------------------------
    # Libraries
    # --------------------------------------------------

    @app.route("/api/libraries", methods=["GET"])
    def libraries():
        return jsonify({"libraries": libs.list_libraries()})

    # --------------------------------------------------
    # Chat
    # --------------------------------------------------

    @app.route("/api/chat", methods=["POST"])
    def chat():
        body = request.get_json(silent=True) or {}
        question = (body.get("question") or "").strip()
        if not question:
            return jsonify({"error": "question is required"}), 400

        history = body.get("history") or ""
        library = body.get("library") or None

        store, _collection, err = _load_for_id(library)
        if err:
            return jsonify({"error": err}), 404

        started = time.time()
        try:
            trace = run_rag(
                question,
                chat_history=history,
                vectorstore=store,
            )
        except Exception as exc:  # noqa: BLE001
            return jsonify({
                "error": f"workflow failed: {exc}",
                "result": "ERROR",
            }), 500

        return jsonify(_trace_response(trace, started))

    # --------------------------------------------------
    # Documents
    # --------------------------------------------------

    @app.route("/api/documents", methods=["GET"])
    def list_documents():
        return jsonify({"documents": libs.list_uploads()})

    @app.route("/api/documents/upload", methods=["POST"])
    def upload_document():
        file = request.files.get("file")
        if not file or not file.filename:
            return jsonify({"error": "a PDF file is required"}), 400
        name = os.path.basename(file.filename)
        if not name.lower().endswith(".pdf"):
            return jsonify({"error": "only PDF files are supported"}), 400

        libs.ensure_dirs()
        file_id = str(uuid.uuid4())
        dest = os.path.join(libs.UPLOAD_DIR, "files", file_id + ".pdf")
        file.save(dest)

        libs.add_upload_entry({
            "store_id": file_id,
            "filename": name,
            "title": os.path.splitext(name)[0],
            "uploaded_at": time.time(),
            "status": "uploaded",
            "chunks": 0,
        })
        return jsonify({"id": file_id, "filename": name, "status": "uploaded"}), 201

    @app.route("/api/documents/process", methods=["POST"])
    def process_document():
        body = request.get_json(silent=True) or {}
        file_id = body.get("id")
        if not file_id:
            return jsonify({"error": "id is required"}), 400

        entry = libs.get_upload_entry(file_id)
        if not entry:
            return jsonify({"error": "unknown document"}), 404

        pdf_path = os.path.join(libs.UPLOAD_DIR, "files", file_id + ".pdf")
        if not os.path.exists(pdf_path):
            return jsonify({"error": "uploaded file missing"}), 404

        from src.ingestion import load_pdf
        from src.chunking import split_documents
        from src.cromaDB import create_vectorstore

        try:
            pages = load_pdf(pdf_path)
            chunks = split_documents(pages)
            if not chunks:
                return jsonify({"error": "no text extracted from PDF"}), 422

            persist = os.path.join(libs.UPLOAD_DIR, "stores", file_id)
            create_vectorstore(
                chunks,
                libs.get_embeddings(),
                collection_name=file_id,
                persist_directory=persist,
            )
            libs.reset_cache()
            libs.remove_upload_entry(file_id)
            libs.add_upload_entry({
                **entry,
                "status": "processed",
                "chunks": len(chunks),
                "store_id": file_id,
                "persist": persist,
            })
            return jsonify({
                "id": file_id,
                "status": "processed",
                "chunks": len(chunks),
            }), 200
        except Exception as exc:  # noqa: BLE001
            libs.remove_upload_entry(file_id)
            libs.add_upload_entry({**entry, "status": "error"})
            return jsonify({"error": f"processing failed: {exc}"}), 500

    @app.route("/api/documents/<file_id>", methods=["DELETE"])
    def delete_document(file_id):
        entry = libs.get_upload_entry(file_id)
        if entry:
            libs.remove_upload_entry(file_id)
        pdf_path = os.path.join(libs.UPLOAD_DIR, "files", file_id + ".pdf")
        persist = os.path.join(libs.UPLOAD_DIR, "stores", file_id)
        for p in (pdf_path, persist):
            import shutil
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.exists(p):
                os.remove(p)
        libs.reset_cache()
        return jsonify({"deleted": file_id})

    return app


app = create_app()


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "5001"))
    app.run(host=host, port=port, threaded=True)
