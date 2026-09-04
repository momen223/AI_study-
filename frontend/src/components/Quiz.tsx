import { useEffect, useRef, useState } from "react";
import {
  ListChecks,
  Loader2,
  Play,
  Send,
  RotateCcw,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  FileText,
} from "lucide-react";
import type {
  CreateQuizInput,
  Difficulty,
  Library,
  Quiz as QuizType,
  QuizResultResponse,
  QuizScoreSummary,
} from "../types";
import { createQuiz, startQuiz, submitQuiz } from "../api";
import { Markdown } from "./Markdown";

const LETTERS = ["A", "B", "C", "D"];

interface QuizProps {
  libraries: Library[];
  selectedId?: string;
  notify: (msg: string, kind?: "ok" | "err") => void;
}

type Phase = "setup" | "intro" | "active" | "result";

export function Quiz({ libraries, selectedId, notify }: QuizProps) {
  const [phase, setPhase] = useState<Phase>("setup");

  // Setup inputs
  const [libraryId, setLibraryId] = useState<string>(selectedId ?? "");
  const [count, setCount] = useState<number>(6);
  const [difficulty, setDifficulty] = useState<Difficulty>("mixed");
  const [topic, setTopic] = useState<string>("");
  const [timeLimit, setTimeLimit] = useState<number>(0);
  const [generating, setGenerating] = useState(false);

  // Session
  const [quiz, setQuiz] = useState<QuizType | null>(null);
  const [attemptId, setAttemptId] = useState<string>("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<QuizResultResponse | null>(null);

  // Timer
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const available = libraries.filter((l) => l.available);

  // Keep the selected library in sync when the App changes it.
  useEffect(() => {
    if (selectedId && !libraryId) setLibraryId(selectedId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  // Clear timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const clearTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setSecondsLeft(null);
  };

  const handleGenerate = async () => {
    if (!libraryId || generating) return;
    setGenerating(true);
    setPhase("setup");
    try {
      const input: CreateQuizInput = {
        library: libraryId,
        question_count: count,
        difficulty,
      };
      if (topic.trim()) input.topic = topic.trim();
      if (timeLimit > 0) input.time_limit_seconds = timeLimit;

      const q = await createQuiz(input);
      setQuiz(q);
      setAnswers({});
      setResult(null);
      setAttemptId("");
      setPhase("intro");
      notify("Quiz generated.", "ok");
    } catch (e) {
      notify((e as Error).message, "err");
    } finally {
      setGenerating(false);
    }
  };

  const handleStart = async () => {
    if (!quiz) return;
    try {
      const started = await startQuiz(quiz.id);
      setAttemptId(started.attempt_id);
      setAnswers({});
      setResult(null);
      setPhase("active");
      if (quiz.time_limit_seconds > 0) {
        setSecondsLeft(quiz.time_limit_seconds);
        timerRef.current = setInterval(() => {
          setSecondsLeft((s) => {
            if (s == null) return s;
            if (s <= 1) {
              // Auto-submit on expiry
              clearInterval(timerRef.current!);
              timerRef.current = null;
              handleSubmit(started.attempt_id, {});
              return 0;
            }
            return s - 1;
          });
        }, 1000);
      }
    } catch (e) {
      notify((e as Error).message, "err");
    }
  };

  const handleSubmit = async (
    aid: string = attemptId,
    override?: Record<string, string>
  ) => {
    if (!quiz) return;
    clearTimer();
    setSubmitting(true);
    try {
      const payload: Record<string, string> = {};
      for (const q of quiz.questions) {
        const chosen = override?.[q.id] ?? answers[q.id];
        if (chosen) payload[q.id] = chosen;
      }
      const res = await submitQuiz(quiz.id, aid, payload);
      setResult(res);
      setPhase("result");
      notify("Answers graded.", "ok");
    } catch (e) {
      setSubmitting(false);
      notify((e as Error).message, "err");
    }
  };

  const resetAll = () => {
    clearTimer();
    setQuiz(null);
    setResult(null);
    setAttemptId("");
    setAnswers({});
    setPhase("setup");
  };

  const mmss = (t: number | null) => {
    if (t == null) return "--:--";
    const m = Math.floor(t / 60);
    const s = t % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  };

  return (
    <div className="section-scroll">
      <div className="section-head">
        <h2>Quizzes</h2>
        <p className="section-sub">
          Generate timed, multiple-choice quizzes grounded in a library's corpus.
          Correct answers are scored authoritatively by the server.
        </p>
      </div>

      {phase === "setup" && (
        <div className="card quiz-setup">
          <div className="panel-section-title">Quiz configuration</div>

          <label className="field">
            <span>Library</span>
            <select
              value={libraryId}
              onChange={(e) => setLibraryId(e.target.value)}
              disabled={generating}
            >
              {!libraryId && <option value="">Select a library…</option>}
              {available.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </label>

          <div className="field-row">
            <label className="field">
              <span>Questions (1–20)</span>
              <input
                type="number"
                min={1}
                max={20}
                value={count}
                onChange={(e) =>
                  setCount(Math.max(1, Math.min(20, Number(e.target.value) || 1)))
                }
                disabled={generating}
              />
            </label>

            <label className="field">
              <span>Difficulty</span>
              <select
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value as Difficulty)}
                disabled={generating}
              >
                <option value="mixed">Mixed</option>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </label>

            <label className="field">
              <span>Time limit (seconds, 0 = none)</span>
              <input
                type="number"
                min={0}
                value={timeLimit}
                onChange={(e) =>
                  setTimeLimit(Math.max(0, Number(e.target.value) || 0))
                }
                disabled={generating}
              />
            </label>
          </div>

          <label className="field">
            <span>Topic (optional)</span>
            <input
              type="text"
              placeholder="e.g. data warehousing, indexing, graph theory…"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              disabled={generating}
            />
          </label>

          {available.length === 0 && (
            <div className="hint-banner">
              No libraries with embedded data are available. Add a document in
              the Documents section or build the demo stores with{" "}
              <code>python scripts/build_vectorstore.py --all</code>.
            </div>
          )}

          <button
            className="btn btn-primary"
            disabled={!libraryId || generating || available.length === 0}
            onClick={handleGenerate}
          >
            {generating ? (
              <Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} />
            ) : (
              <ListChecks size={16} />
            )}
            {generating ? "Generating…" : "Generate quiz"}
          </button>
        </div>
      )}

      {phase === "intro" && quiz && (
        <div className="card">
          <div className="quiz-title">
            <span className="quiz-emoji">📋</span>
            <div>
              <h3>{quiz.title || `${quiz.subject} quiz`}</h3>
              <div className="quiz-meta">
                <span className="result-badge result-ok">{quiz.status}</span>
                <span> {quiz.question_count} questions</span>
                <span> · {quiz.difficulty}</span>
                {quiz.time_limit_seconds > 0 && (
                  <span> · {quiz.time_limit_seconds}s limit</span>
                )}
              </div>
            </div>
          </div>

          <p className="tr-text">
            Each question has four choices. Your answers are submitted to the
            server which scores them against the authoritative key. You cannot
            see the correct answers before submitting.
          </p>

          <div className="quiz-actions">
            <button className="btn btn-primary" onClick={handleStart}>
              <Play size={16} /> Start quiz
            </button>
            <button className="btn" onClick={resetAll}>
              <RotateCcw size={16} /> Discard
            </button>
          </div>
        </div>
      )}

      {phase === "active" && quiz && (
        <div className="card">
          <div className="quiz-active-head">
            <div>
              <h3>{quiz.title || `${quiz.subject} quiz`}</h3>
              <div className="quiz-meta">
                {quiz.question_count} questions · {quiz.difficulty}
              </div>
            </div>
            {secondsLeft != null && (
              <span className={`timer ${secondsLeft <= 30 ? "timer-warn" : ""}`}>
                <Clock size={16} /> {mmss(secondsLeft)}
              </span>
            )}
          </div>

          {quiz.questions.map((q, qi) => (
            <div className="quiz-question" key={q.id}>
              <div className="quiz-q-head">
                <span className="quiz-q-num">Q{qi + 1}</span>
                <span className="quiz-q-diff">{q.difficulty}</span>
              </div>
              <div className="quiz-q-prompt">{q.prompt}</div>
              <div className="quiz-options">
                {q.options.map((opt, oi) => {
                  const key = `${q.id}`;
                  const chosen = answers[key] === LETTERS[oi];
                  return (
                    <button
                      key={oi}
                      className={`quiz-option ${chosen ? "chosen" : ""}`}
                      onClick={() =>
                        setAnswers((a) => ({ ...a, [key]: LETTERS[oi] }))
                      }
                    >
                      <span className="quiz-opt-letter">{LETTERS[oi]}</span>
                      <span className="quiz-opt-text">{opt}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}

          <div className="quiz-actions">
            <button
              className="btn btn-primary"
              disabled={submitting}
              onClick={() => handleSubmit()}
            >
              <Send size={16} />
              {submitting ? "Submitting…" : "Submit answers"}
            </button>
          </div>
        </div>
      )}

      {phase === "result" && quiz && result && (
        <ResultView quiz={quiz} result={result} onNew={resetAll} />
      )}
    </div>
  );
}

function ResultView({
  quiz,
  result,
  onNew,
}: {
  quiz: QuizType;
  result: QuizResultResponse;
  onNew: () => void;
}) {
  const score: QuizScoreSummary = result.score;
  const correctMap = score.correct ?? {};
  const pct =
    score.total > 0 ? Math.round((score.score / score.total) * 100) : 0;

  const gradeCls =
    pct >= 80 ? "result-ok" : pct >= 50 ? "result-rate" : "result-error";
  const gradeLabel = pct >= 80 ? "Excellent" : pct >= 50 ? "Good" : "Keep studying";

  return (
    <div className="card">
      <div className="result-hero">
        <div className={`result-ring ${gradeCls}`}>
          <div className="result-ring-inner">
            <strong>{score.score}</strong>
            <span>/ {score.total}</span>
          </div>
        </div>
        <div>
          <div className={`result-badge ${gradeCls}`}>{gradeLabel}</div>
          <div className="result-sub">
            {pct}% · {score.answered} answered ·{" "}
            {result.result === "COMPLETED" ? "Completed" : "Partial"}
          </div>
          {result.attempt.timed_out && (
            <div className="hint-banner">
              <AlertTriangle size={13} /> The time limit expired; unanswered
              questions were counted as incorrect.
            </div>
          )}
        </div>
      </div>

      {quiz.questions.map((q, qi) => {
        const letter = q.correct_letter ?? "—";
        const chosen = result.attempt.answers[q.id];
        const ok = correctMap[q.id] === true;
        return (
          <div className="quiz-question graded" key={q.id}>
            <div className="quiz-q-head">
              <span className="quiz-q-num">Q{qi + 1}</span>
              {ok ? (
                <span className="grade-pill ok">
                  <CheckCircle2 size={13} /> Correct
                </span>
              ) : (
                <span className="grade-pill no">
                  <XCircle size={13} /> {chosen ? "Incorrect" : "Unanswered"}
                </span>
              )}
            </div>
            <div className="quiz-q-prompt">{q.prompt}</div>
            <div className="quiz-options static">
              {q.options.map((opt, oi) => {
                const optLetter = LETTERS[oi];
                const isCorrect = optLetter === letter;
                const isChosen = chosen === optLetter;
                let cls = "quiz-option";
                if (isCorrect) cls += " correct";
                else if (isChosen) cls += " wrong";
                return (
                  <div className={cls} key={oi}>
                    <span className="quiz-opt-letter">{optLetter}</span>
                    <span className="quiz-opt-text">{opt}</span>
                    {isCorrect && <CheckCircle2 size={15} className="mark ok" />}
                    {isChosen && !isCorrect && (
                      <XCircle size={15} className="mark no" />
                    )}
                  </div>
                );
              })}
            </div>
            {(q.explanation || q.evidence) && (
              <div className="quiz-explain">
                <div className="tr-label">Explanation</div>
                {q.explanation ? (
                  <Markdown content={q.explanation} />
                ) : (
                  <div className="tr-text">No explanation provided.</div>
                )}
                {q.evidence && (
                  <>
                    <div className="tr-label" style={{ marginTop: 8 }}>
                      Evidence from source
                    </div>
                    <blockquote className="evidence">
                      <FileText size={13} />
                      <span>{q.evidence}</span>
                    </blockquote>
                  </>
                )}
              </div>
            )}
          </div>
        );
      })}

      <div className="quiz-actions">
        <button className="btn btn-primary" onClick={onNew}>
          <RotateCcw size={16} /> New quiz
        </button>
      </div>
    </div>
  );
}
