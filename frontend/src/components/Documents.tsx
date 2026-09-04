import { useEffect, useRef, useState } from "react";
import type { UploadDoc } from "../types";
import {
  FileText,
  X,
  Play,
  Trash2,
  Database,
  Loader2,
  UploadCloud,
} from "lucide-react";
import {
  listDocuments,
  uploadDocument,
  processDocument,
  deleteDocument,
} from "../api";

interface DocumentsProps {
  open: boolean;
  onClose: () => void;
  onChanged: () => void;
  notify: (msg: string, kind?: "ok" | "err") => void;
}

export function Documents({ open, onClose, onChanged, notify }: DocumentsProps) {
  const [docs, setDocs] = useState<UploadDoc[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = async () => {
    try {
      const d = await listDocuments();
      setDocs(d);
    } catch (e) {
      notify((e as Error).message, "err");
    }
  };

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    refresh().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;

  const handleFile = async (file?: File | null) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      notify("Only PDF files are supported", "err");
      return;
    }
    setBusy("upload");
    try {
      await uploadDocument(file);
      notify("Uploaded.", "ok");
      await refresh();
      onChanged();
    } catch (e) {
      notify((e as Error).message, "err");
    } finally {
      setBusy(null);
    }
  };

  const handleProcess = async (id: string) => {
    setBusy(id);
    try {
      await processDocument(id);
      notify("Document embedded into a new library.", "ok");
      await refresh();
      onChanged();
    } catch (e) {
      notify((e as Error).message, "err");
    } finally {
      setBusy(null);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteDocument(id);
      setDocs((d) => d.filter((x) => x.store_id !== id));
      notify("Document removed.", "ok");
      onChanged();
    } catch (e) {
      notify((e as Error).message, "err");
    }
  };

  return (
    <div className="panel-overlay" onClick={onClose}>
      <div className="panel" onClick={(e) => e.stopPropagation()}>
        <div className="panel-head">
          <h3>
            <Database size={18} style={{ marginRight: 8 }} />
            Documents
          </h3>
          <button className="icon-btn" onClick={onClose} title="Close">
            <X size={17} />
          </button>
        </div>

        <div
          className={`upload-zone ${drag ? "drag" : ""}`}
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            handleFile(e.dataTransfer.files?.[0]);
          }}
        >
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,application/pdf"
            hidden
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          <UploadCloud size={26} style={{ margin: "0 auto 8px", color: "var(--accent-text)" }} />
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>
            {busy === "upload" ? "Uploading…" : "Upload a PDF"}
          </div>
          <div className="drop-hint">
            Click to browse or drop a PDF. After uploading, press Process to embed it
            into a new library you can chat against.
          </div>
        </div>

        <div className="panel-section-title">Uploaded documents</div>
        <div className="doc-list">
          {loading && docs.length === 0 && (
            <div className="tr-text" style={{ textAlign: "center", padding: 12 }}>
              <Loader2 size={20} style={{ animation: "spin 1s linear infinite" }} />
            </div>
          )}
          {!loading && docs.length === 0 && (
            <div className="tr-text" style={{ textAlign: "center", color: "var(--text-3)", padding: 12 }}>
              No documents yet.
            </div>
          )}
          {docs.map((d) => (
            <div className="doc-item" key={d.store_id}>
              <FileText className="file-icon" size={20} />
              <div className="doc-info">
                <div className="doc-name">{d.filename}</div>
                <div className="doc-meta">
                  {d.chunks > 0 ? `${d.chunks} chunks · ` : ""}
                  {new Date(d.uploaded_at * 1000).toLocaleString()}
                </div>
              </div>
              <span className={`status-pill status-${d.status}`}>
                {d.status === "uploaded" ? "Uploaded" : d.status === "processed" ? "Processed" : "Error"}
              </span>
              <div className="doc-actions">
                {d.status !== "processed" && (
                  <button
                    className="mini-btn"
                    onClick={() => handleProcess(d.store_id)}
                    disabled={busy === d.store_id}
                    title="Process / embed"
                  >
                    <Play size={13} /> {busy === d.store_id ? "…" : "Process"}
                  </button>
                )}
                <button className="mini-btn" onClick={() => handleDelete(d.store_id)} title="Delete">
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
