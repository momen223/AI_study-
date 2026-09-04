import { useCallback, useEffect, useRef, useState } from "react";
import {
  Moon,
  Sun,
  Send,
  Sparkles,
  FolderOpen,
  PanelLeftClose,
  PanelLeftOpen,
  Bot,
} from "lucide-react";
import type { ChatResponse, Library } from "./types";
import { chat, getLibraries } from "./api";
import { UserMessage, AssistantMessage } from "./components/Message";
import { Transparency } from "./components/Transparency";
import { Documents } from "./components/Documents";
import { Sidebar, type Section } from "./components/Sidebar";
import { Quiz } from "./components/Quiz";
import { Sources } from "./components/Sources";
import { Settings } from "./components/Settings";

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse | null;
  error?: string | null;
}

const SUGGESTIONS = [
  "What is a data warehouse?",
  "Explain the difference between a fact table and a dimension table.",
  "What is ETL?",
];

let mid = 1;

export default function App() {
  const { mode, toggle } = useTheme();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [library, setLibrary] = useState<string | undefined>(undefined);
  const [docOpen, setDocOpen] = useState(false);
  const [snackbar, setSnackbar] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [section, setSection] = useState<Section>("chat");
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const notify = useCallback((msg: string) => {
    setSnackbar(msg);
    window.setTimeout(() => setSnackbar(null), 4200);
  }, []);

  const loadLibraries = useCallback(async () => {
    try {
      const libs = await getLibraries();
      setLibraries(libs);
      const avail = libs.filter((l) => l.available);
      setLibrary((cur) => {
        if (cur && libs.some((l) => l.id === cur)) return cur;
        return avail[0]?.id ?? libs[0]?.id;
      });
    } catch (e) {
      notify((e as Error).message);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadLibraries();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (section === "chat") {
      scrollRef.current?.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages, loading, section]);

  const selected = libraries.find((l) => l.id === library);

  const buildHistory = (): string => {
    const recent = messages.slice(-8);
    return recent
      .map((m) => `${m.role === "user" ? "User" : "Assistant"}: ${m.content}`)
      .join("\n");
  };

  const send = async (textOverride?: string) => {
    const q = (textOverride ?? input).trim();
    if (!q || loading) return;
    setInput("");
    setLoading(true);
    const userMsg: Message = { id: mid++, role: "user", content: q };
    const placeholder: Message = { id: mid++, role: "assistant", content: "" };
    setMessages((m) => [...m, userMsg, placeholder]);

    try {
      const res = await chat({ question: q, history: buildHistory(), library });
      setMessages((m) =>
        m.map((msg) =>
          msg.id === placeholder.id
            ? {
                ...msg,
                content: res.answer || "No answer returned.",
                response: res,
              }
            : msg
        )
      );
    } catch (e) {
      setMessages((m) =>
        m.map((msg) =>
          msg.id === placeholder.id ? { ...msg, error: (e as Error).message } : msg
        )
      );
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  };

  const regenerate = (id: number) => {
    const idx = messages.findIndex((m) => m.id === id);
    if (idx < 1) return;
    const userMsg = messages[idx - 1];
    if (userMsg?.role !== "user") return;
    setMessages(messages.slice(0, idx - 1));
    send(userMsg.content);
  };

  const clearAll = () => {
    if (messages.length === 0) return;
    setMessages([]);
    notify("Conversation cleared.");
  };

  const navigate = (sec: Section) => {
    setSection(sec);
    if (sec === "documents") setDocOpen(true);
  };

  return (
    <div className="app">
      <Sidebar
        libraries={libraries}
        selected={selected}
        onSelect={setLibrary}
        onClear={clearAll}
        onToggleTheme={toggle}
        mode={mode}
        section={section}
        onNavigate={navigate}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="main">
        <header className="app-header">
          <button
            className="icon-btn sidebar-toggle"
            title={sidebarOpen ? "Close sidebar" : "Open sidebar"}
            onClick={() => setSidebarOpen((o) => !o)}
          >
            {sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
          </button>

          <div className="brand">
            <span className="brand-badge">
              <Sparkles size={20} />
            </span>
            <div className="brand-text">
              <span className="brand-name">Agentic RAG Studio</span>
              <span className="brand-sub">
                {section === "chat"
                  ? selected
                    ? selected.name
                    : "Select a library"
                  : section[0].toUpperCase() + section.slice(1)}
              </span>
            </div>
          </div>

          <div className="header-spacer" />

          {section === "chat" && (
            <button
              className="icon-btn"
              title="Manage documents"
              onClick={() => setDocOpen(true)}
            >
              <FolderOpen size={18} />
            </button>
          )}
          <button className="icon-btn" title="Toggle theme" onClick={toggle}>
            {mode === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </header>

        {section === "chat" && (
          <div className="chat-shell">
            <div className="messages" ref={scrollRef}>
              {messages.length === 0 && !loading && (
                <div className="empty-state">
                  <div className="glyph">
                    <Bot size={30} />
                  </div>
                  <h2>Ask grounded questions over your documents</h2>
                  <p>
                    Every answer runs through an agentic workflow — query
                    understanding, retrieval, relevance checking, answer
                    generation, and grounding verification — so results are
                    traced and backed by real sources.
                  </p>
                  <div className="prompt-chips">
                    {SUGGESTIONS.map((s) => (
                      <button key={s} className="chip" onClick={() => send(s)}>
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((m) =>
                m.role === "user" ? (
                  <UserMessage key={m.id} role="user" content={m.content} />
                ) : m.error ? (
                  <div
                    key={m.id}
                    className="msg assistant"
                    style={{ flexDirection: "column" }}
                  >
                    <AssistantMessage
                      role="assistant"
                      content=""
                      response={null}
                    />
                    <div className="msg-body">
                      <div className="result-badge result-error">Error</div>
                      <p className="tr-text">{m.error}</p>
                    </div>
                  </div>
                ) : m.content === "" && !m.response ? (
                  <div
                    key={m.id}
                    className="msg assistant"
                    style={{ flexDirection: "column" }}
                  >
                    <div className="msg-role">
                      <span className="msg-avatar">
                        <Sparkles size={16} />
                      </span>
                      <span style={{ marginLeft: 10 }}>Assistant</span>
                    </div>
                    <div className="msg-body">
                      <div className="typing">
                        <span />
                        <span />
                        <span />
                      </div>
                    </div>
                  </div>
                ) : (
                  <div
                    key={m.id}
                    className="msg assistant"
                    style={{ flexDirection: "column" }}
                  >
                    <AssistantMessage
                      role="assistant"
                      content={m.content}
                      response={m.response}
                      onRegenerate={() => regenerate(m.id)}
                    />
                    {m.response && (
                      <div className="msg-body">
                        <Transparency response={m.response} />
                      </div>
                    )}
                  </div>
                )
              )}
            </div>

            <div className="composer">
              <div className="composer-inner">
                <textarea
                  ref={textareaRef}
                  value={input}
                  rows={1}
                  placeholder="Ask a question about the selected library…"
                  onChange={(e) => {
                    setInput(e.target.value);
                    e.target.style.height = "auto";
                    e.target.style.height =
                      Math.min(e.target.scrollHeight, 160) + "px";
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      send();
                    }
                  }}
                />
                <button
                  className="send-btn"
                  disabled={!input.trim() || loading}
                  onClick={() => send()}
                >
                  <Send size={18} />
                </button>
              </div>
              {selected && !selected.available && (
                <div className="hint-banner">
                  The selected library has no embedded data yet. Process a
                  document in the{" "}
                  <button
                    className="mini-btn"
                    style={{ marginLeft: 4 }}
                    onClick={() => setDocOpen(true)}
                  >
                    Documents
                  </button>{" "}
                  manager, or build the demo stores with{" "}
                  <code>python scripts/build_vectorstore.py --all</code>.
                </div>
              )}
              <div className="composer-foot">
                <span>
                  {selected
                    ? `Library: ${selected.name}`
                    : "No library selected"}
                  · Enter to send, Shift+Enter for a new line
                </span>
              </div>
            </div>
          </div>
        )}

        {section === "quiz" && (
          <Quiz libraries={libraries} selectedId={library} notify={notify} />
        )}

        {section === "sources" && (
          <Sources libraries={libraries} history={messages} />
        )}

        {section === "settings" && (
          <Settings mode={mode} onToggleTheme={toggle} />
        )}

        {section === "documents" && (
          <div className="section-scroll">
            <div className="section-head">
              <h2>Documents</h2>
              <p className="section-sub">
                Upload PDFs and embed them as their own library so you can chat
                against them.
              </p>
            </div>
            <button
              className="btn btn-primary"
              style={{ alignSelf: "flex-start" }}
              onClick={() => setDocOpen(true)}
            >
              <FolderOpen size={16} /> Open document manager
            </button>
          </div>
        )}
      </div>

      <Documents
        open={docOpen}
        onClose={() => setDocOpen(false)}
        onChanged={loadLibraries}
        notify={notify}
      />

      {snackbar && <div className="snackbar">{snackbar}</div>}
    </div>
  );
}

function useTheme() {
  const [mode, setMode] = useState<"light" | "dark">(() =>
    window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
  );
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", mode);
  }, [mode]);
  return {
    mode,
    toggle: () => setMode((m) => (m === "dark" ? "light" : "dark")),
  };
}
