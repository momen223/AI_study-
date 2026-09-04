import { useState, useEffect } from "react";
import {
  MessageSquare,
  Database,
  Moon,
  Sun,
  Trash2,
  Sparkles,
  ChevronRight,
  Library as LibraryIcon,
  X,
  ListChecks,
  BookOpen,
  Settings,
} from "lucide-react";
import type { Library } from "../types";

export type Section = "chat" | "quiz" | "documents" | "sources" | "settings";

interface SidebarProps {
  libraries: Library[];
  selected?: Library;
  onSelect: (id: string) => void;
  onClear: () => void;
  onToggleTheme: () => void;
  mode: "light" | "dark";
  section: Section;
  onNavigate: (section: Section) => void;
  open: boolean;
  onClose: () => void;
}

interface NavReset {
  (): void;
}

export function Sidebar({
  libraries,
  selected,
  onSelect,
  onClear,
  onToggleTheme,
  mode,
  section,
  onNavigate,
  open,
  onClose,
}: SidebarProps) {
  const [showLibraries, setShowLibraries] = useState(false);

  // Close sidebar on escape key
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) onClose();
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [open, onClose]);

  // Prevent body scroll when sidebar is open on mobile
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  const go = (s: Section): NavReset => {
    onNavigate(s);
    setShowLibraries(false);
    onClose();
    return () => {};
  };

  const navItem = (active: boolean) =>
    `nav-item${active ? " nav-active" : ""}`;

  return (
    <>
      {/* Mobile backdrop */}
      {open && (
        <div
          className="sidebar-backdrop"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <span className="brand-badge">
              <Sparkles size={20} />
            </span>
            <div className="brand-text">
              <span className="brand-name">RAG Studio</span>
              <span className="brand-sub">Agentic Retrieval</span>
            </div>
          </div>
          <button
            className="icon-btn sidebar-close"
            onClick={onClose}
            title="Close sidebar"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section">
            <div className="nav-section-title">Learn</div>
            <button
              className={navItem(section === "chat")}
              onClick={() => go("chat")}
            >
              <MessageSquare size={18} />
              <span>Chat</span>
            </button>
            <button
              className={navItem(section === "quiz")}
              onClick={() => go("quiz")}
            >
              <ListChecks size={18} />
              <span>Quizzes</span>
            </button>
            <button
              className={navItem(section === "sources")}
              onClick={() => go("sources")}
            >
              <BookOpen size={18} />
              <span>Sources</span>
            </button>
          </div>

          <div className="nav-section">
            <div className="nav-section-title">Manage</div>
            <button
              className={navItem(section === "documents")}
              onClick={() => go("documents")}
            >
              <Database size={18} />
              <span>Documents</span>
            </button>
            <button
              className={navItem(section === "settings")}
              onClick={() => go("settings")}
            >
              <Settings size={18} />
              <span>Settings</span>
            </button>
          </div>

          <div className="nav-section">
            <div className="nav-section-title">Libraries</div>
            <button
              className="nav-item nav-item-expand"
              onClick={() => setShowLibraries((o) => !o)}
            >
              <LibraryIcon size={18} />
              <span>Collections</span>
              <ChevronRight
                size={16}
                className={`chevron ${showLibraries ? "chevron-open" : ""}`}
              />
            </button>
            {showLibraries && (
              <div className="library-list">
                {libraries.map((lib) => (
                  <button
                    key={lib.id}
                    className={`library-list-item ${
                      selected?.id === lib.id ? "active" : ""
                    } ${!lib.available ? "unavailable" : ""}`}
                    onClick={() => {
                      onSelect(lib.id);
                      setShowLibraries(false);
                      onNavigate("chat");
                      onClose();
                    }}
                  >
                    <span className="library-list-name">{lib.name}</span>
                    <span
                      className={`library-list-status ${
                        lib.available ? "ready" : "missing"
                      }`}
                    >
                      {lib.available ? "Ready" : "No data"}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </nav>

        <div className="sidebar-footer">
          <button
            className="nav-item"
            onClick={() => {
              onClear();
              onClose();
            }}
            title="Clear conversation"
          >
            <Trash2 size={18} />
            <span>Clear chat</span>
          </button>
          <button
            className="nav-item"
            onClick={() => {
              onToggleTheme();
              onClose();
            }}
            title={`Switch to ${mode === "dark" ? "light" : "dark"} mode`}
          >
            {mode === "dark" ? (
              <Sun size={18} />
            ) : (
              <Moon size={18} />
            )}
            <span>{mode === "dark" ? "Light mode" : "Dark mode"}</span>
          </button>
        </div>
      </aside>
    </>
  );
}
