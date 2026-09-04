import { useMemo, useState } from "react";
import {
  BookOpen,
  Database,
  Search,
  FileText,
  Globe,
  Loader2,
} from "lucide-react";
import type { ChatResponse, Library } from "../types";

interface SourcesProps {
  libraries: Library[];
  history: { response?: ChatResponse | null }[];
}

type SourceItem = {
  name: string;
  count: number;
  citations: {
    page?: number | null;
    score: number | null;
    snippet: string;
  }[];
};

export function Sources({ libraries, history }: SourcesProps) {
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const { sources, totalCites, totalMsgs } = useMemo(() => {
    const map = new Map<string, SourceItem>();
    let cites = 0;
    let msgs = 0;
    for (const item of history) {
      const response = item.response;
      if (!response) continue;
      msgs += 1;
      for (const c of response.citations || []) {
        cites += 1;
        let entry = map.get(c.source);
        if (!entry) {
          entry = { name: c.source, count: 0, citations: [] };
          map.set(c.source, entry);
        }
        entry.count += 1;
        entry.citations.push({ page: c.page, score: c.score, snippet: c.snippet });
      }
    }
    return { sources: Array.from(map.values()), totalCites: cites, totalMsgs: msgs };
  }, [history]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return sources;
    return sources.filter((s) => s.name.toLowerCase().includes(q));
  }, [sources, query]);

  return (
    <div className="section-scroll">
      <div className="section-head">
        <h2>Sources</h2>
        <p className="section-sub">
          Every citation the assistant surfaced across your conversation,
          aggregated by source document.
        </p>
      </div>

      <div className="sources-summary">
        <div className="stat-chip">
          <BookOpen size={15} />
          <strong>{sources.length}</strong> source documents
        </div>
        <div className="stat-chip">
          <Search size={15} />
          <strong>{totalCites}</strong> citations
        </div>
        <div className="stat-chip">
          <Globe size={15} />
          <strong>{totalMsgs}</strong> answered messages
        </div>
      </div>

      <div className="search-bar">
        <Search size={15} />
        <input
          type="text"
          placeholder="Filter by document name…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">
          <Loader2 size={18} className="spin" />
          <p>
            {history.length === 0
              ? "No sources yet. Ask a question in the Chat section and citations will appear here."
              : query
              ? "No sources match that name."
              : "No citations found in this conversation."}
          </p>
        </div>
      ) : (
        <div className="source-list">
          {filtered.map((s) => {
            const open = expanded === s.name;
            return (
              <div className="card source-card" key={s.name}>
                <button
                  className="source-card-head"
                  onClick={() => setExpanded(open ? null : s.name)}
                >
                  <FileText size={17} />
                  <span className="source-name">{s.name}</span>
                  <span className="source-count">{s.count} citations</span>
                </button>
                {open && (
                  <div className="source-card-body">
                    {s.citations.map((c, i) => (
                      <div className="source-citation" key={i}>
                        <div className="source-cite-meta">
                          <span>Page {c.page ?? "?"}</span>
                          <span className="score">
                            relevance{" "}
                            {c.score != null ? c.score.toFixed(3) : "n/a"}
                          </span>
                        </div>
                        <p className="source-snippet">{c.snippet}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="section-spacer" />

      <div className="panel-section-title">Available libraries</div>
      <div className="library-cards">
        {libraries.map((lib) => (
          <div className="card library-card" key={lib.id}>
            <div className="library-card-name">
              <Database size={16} />
              <span>{lib.name}</span>
              <span
                className={`library-list-status ${
                  lib.available ? "ready" : "missing"
                }`}
              >
                {lib.available ? "Ready" : "No data"}
              </span>
            </div>
            <div className="library-card-type">{lib.type}</div>
            <code className="library-card-collection">{lib.collection}</code>
          </div>
        ))}
      </div>
    </div>
  );
}
