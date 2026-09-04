import type { ChatResponse } from "../types";
import {
  Eye,
  FileText,
  Scale,
  BadgeCheck,
  Timer,
} from "lucide-react";

function relevanceClass(verdict?: string | null) {
  if (!verdict) return "";
  const v = verdict.toLowerCase();
  if (v.startsWith("relevant")) return "relevant";
  if (v.startsWith("not_relevant") || v.startsWith("not")) return "not-relevant";
  if (v.startsWith("borderline") || v.startsWith("uncertain")) return "borderline";
  return "";
}

function groundingClass(verdict?: string | null) {
  if (!verdict) return "";
  if (verdict.toLowerCase().startsWith("grounded")) return "grounded";
  return "skipped";
}

interface TransparencyProps {
  response: ChatResponse;
}

export function Transparency({ response }: TransparencyProps) {
  const r = response.relevance;
  const g = response.grounding;
  const hasRelevance = r?.verdict;
  const hasGrounding = g?.verdict || g?.status;
  const hasReason = r?.reason;
  const citations = response.citations || [];

  return (
    <details className="transparency">
      <summary>
        <Eye size={15} />
        <span className="transparency-summary-text">How this answer was produced</span>
      </summary>
      <div className="transparency-panel">
        <div className="tr-verdict">
          {response.intent && (
            <span className="verdict-pill">
              <Scale size={13} />
              <span>Intent:</span>
              <strong>{response.intent}</strong>
            </span>
          )}
          {response.rewrote && (
            <span className="verdict-pill">
              <Scale size={13} /> Rewritten question
            </span>
          )}
          {response.standalone_question && (
            <div className="tr-full">
              <div className="tr-label">Standalone question</div>
              <div className="tr-text">{response.standalone_question}</div>
            </div>
          )}
          {hasRelevance && (
            <span className={`verdict-pill ${relevanceClass(r.verdict)}`}>
              <Scale size={13} /> Relevance: <strong>{r.verdict}</strong>
            </span>
          )}
          {hasGrounding && (
            <span className={`verdict-pill ${groundingClass(g.verdict)}`}>
              <BadgeCheck size={13} /> Grounding: <strong>{g.verdict || g.status}</strong>
            </span>
          )}
        </div>

        {hasReason && (
          <div>
            <div className="tr-label">Relevance reasoning</div>
            <div className="tr-text">{r.reason}</div>
          </div>
        )}

        {r?.best_score != null && (
          <div className="tr-verdict">
            <span className="verdict-pill">
              Best similarity: <strong>{formatScore(r.best_score)}</strong>
            </span>
            {r.strong_count != null && (
              <span className="verdict-pill">
                Strong chunks: <strong>{r.strong_count}</strong>
              </span>
            )}
            {r.relevant_count != null && (
              <span className="verdict-pill">
                Relevant chunks: <strong>{r.relevant_count}</strong>
              </span>
            )}
          </div>
        )}

        {citations.length > 0 && (
          <div>
            <div className="tr-label">
              <FileText size={13} style={{ verticalAlign: -2, marginRight: 4 }} />
              Sources ({citations.length})
            </div>
            <div className="citations">
              {citations.map((c, i) => (
                <div className="citation" key={i}>
                  <div className="citation-head">
                    <span className="citation-title">📄 {basename(c.source)}</span>
                    {c.page != null && <span className="citation-meta">· p.{c.page}</span>}
                    {c.score != null && (
                      <span className="score">d={formatScore(c.score)}</span>
                    )}
                  </div>
                  <div className="citation-snippet">{c.snippet}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="tr-footer">
          <Timer size={12} />
          <span>Processed in {response.processing_ms} ms</span>
        </div>
      </div>
    </details>
  );
}

function basename(path: string): string {
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1] || path;
}

function formatScore(n: number): string {
  return n.toFixed(3);
}
