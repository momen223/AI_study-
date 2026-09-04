import { useState } from "react";
import type { ChatResponse } from "../types";
import { Markdown } from "./Markdown";
import {
  Check,
  Copy,
  RotateCcw,
  Sparkles,
  HelpCircle,
  Clock,
  AlertTriangle,
  ShieldCheck,
} from "lucide-react";

interface MessageProps {
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse | null;
  onRegenerate?: () => void;
}

function resultBadge(result: string) {
  switch (result) {
    case "ANSWERED":
      return {
        cls: "result-ok",
        label: "Answered",
        icon: <ShieldCheck size={13} />,
      };
    case "UNKNOWN":
    case "NOT_RELEVANT":
      return {
        cls: "result-unknown",
        label: "No answer in context",
        icon: <HelpCircle size={13} />,
      };
    case "RATE_LIMITED":
      return {
        cls: "result-rate",
        label: "Rate limited",
        icon: <Clock size={13} />,
      };
    default:
      return {
        cls: "result-error",
        label: "Error",
        icon: <AlertTriangle size={13} />,
      };
  }
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useCopied();
  return (
    <button
      className="mini-btn"
      onClick={() => {
        navigator.clipboard.writeText(text).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1400);
        });
      }}
      title="Copy"
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

// tiny useState helper to avoid importing React namespace repeatedly
function useCopied() {
  const [copied, setCopied] = useState(false);
  return [copied, setCopied] as const;
}

export function AssistantMessage({
  response,
  content,
  onRegenerate,
}: MessageProps) {
  const badge = response ? resultBadge(response.result) : null;
  return (
    <div className="msg assistant">
      <div className="msg-role">
        <span className="msg-avatar">
          <Sparkles size={16} />
        </span>
        <span style={{ marginLeft: 10 }}>Assistant</span>
      </div>
      <div className="msg-body">
        {badge && (
          <span className={`result-badge ${badge.cls}`}>
            {badge.icon}
            {badge.label}
          </span>
        )}
        <Markdown content={content} />
        {response && (
          <div className="msg-actions">
            <CopyButton text={content} />
            {onRegenerate && (
              <button
                className="mini-btn"
                onClick={onRegenerate}
                title="Regenerate"
              >
                <RotateCcw size={13} /> Regenerate
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function UserMessage({ content }: MessageProps) {
  return (
    <div className="msg user">
      <span className="msg-avatar">
        <span style={{ fontSize: 15 }}>🧑‍💻</span>
      </span>
      <div className="msg-body">{content}</div>
    </div>
  );
}
