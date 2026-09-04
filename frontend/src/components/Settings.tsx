import { useEffect, useState } from "react";
import {
  Moon,
  Sun,
  Info,
  Activity,
  CheckCircle2,
  XCircle,
  Cog,
  Shield,
} from "lucide-react";
import { getHealth } from "../api";

interface SettingsProps {
  mode: "light" | "dark";
  onToggleTheme: () => void;
}

export function Settings({ mode, onToggleTheme }: SettingsProps) {
  const [health, setHealth] = useState<
    { status: string; service: string } | "loading" | null
  >(null);

  useEffect(() => {
    let alive = true;
    getHealth()
      .then((h) => alive && setHealth(h))
      .catch(() => alive && setHealth(null));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="section-scroll">
      <div className="section-head">
        <h2>Settings</h2>
        <p className="section-sub">
          Appearance preferences and information about the local Agentic RAG
          backend.
        </p>
      </div>

      <div className="card">
        <div className="panel-section-title">
          <Cog size={16} /> Appearance
        </div>
        <div className="setting-row">
          <div>
            <div className="setting-title">Theme</div>
            <div className="setting-desc">
              Switch between the light and dark color scheme.
            </div>
          </div>
          <button className="btn" onClick={onToggleTheme}>
            {mode === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            {mode === "dark" ? "Light mode" : "Dark mode"}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="panel-section-title">
          <Activity size={16} /> Backend
        </div>
        <div className="setting-row">
          <div>
            <div className="setting-title">API health</div>
            <div className="setting-desc">
              Proxied through the Vite dev server to{" "}
              <code>127.0.0.1:5001</code>. Start it with{" "}
              <code>python api/app.py</code>.
            </div>
          </div>
          {health === "loading" ? (
            <span className="health-pill loading">Checking…</span>
          ) : health ? (
            <span className="health-pill ok">
              <CheckCircle2 size={13} /> {health.service} · {health.status}
            </span>
          ) : (
            <span className="health-pill bad">
              <XCircle size={13} /> Offline
            </span>
          )}
        </div>
      </div>

      <div className="card">
        <div className="panel-section-title">
          <Info size={16} /> About
        </div>
        <div className="setting-row">
          <div>
            <div className="setting-title">Agentic RAG Studio</div>
            <div className="setting-desc">
              Retrieval-augmented generation with intent rewriting, relevance
              grounding, and question generation. The core RAG pipeline is
              served by the Flask API; the UI is a Vite + React client.
            </div>
          </div>
        </div>
        <div className="setting-row">
          <div>
            <div className="setting-title">
              <Shield size={14} /> Safety model
            </div>
            <div className="setting-desc">
              The API exposes only structured workflow metadata (verdicts,
              scores, citations) — never raw chain-of-thought — and never
              returns ungrounded content.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
