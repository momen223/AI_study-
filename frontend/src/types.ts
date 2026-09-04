export interface Library {
  id: string;
  name: string;
  collection: string;
  persist: string;
  default: boolean;
  available: boolean;
  type: "primary" | "subject" | "upload";
  documents?: UploadDoc[];
}

export interface UploadDoc {
  store_id: string;
  filename: string;
  title: string;
  uploaded_at: number;
  status: "uploaded" | "processed" | "error";
  chunks: number;
}

export interface Citation {
  source: string;
  page: number | null | undefined;
  score: number | null;
  snippet: string;
}

export interface RelevanceMeta {
  verdict: string | null;
  reason: string | null;
  best_score: number | null;
  strong_count: number | null;
  relevant_count: number | null;
}

export interface GroundingMeta {
  verdict: string | null;
  status: string | null;
}

export interface ChatResponse {
  answer: string;
  result: string;
  error?: string | null;
  standalone_question?: string | null;
  intent?: string | null;
  rewrote: boolean;
  query_error: boolean;
  relevance: RelevanceMeta;
  grounding: GroundingMeta;
  citations: Citation[];
  sources: string[];
  processing_ms: number;
  is_unknown: boolean;
}

/* -------------------------------------------------------------
   Quiz types — mirror the backend `src/quizzes/*` models.
   Correct answers are ONLY present after submission/grading.
   ------------------------------------------------------------- */

export type GenerationStatus = "READY" | "PARTIAL" | "ERROR" | "CANCELLED";
export type AttemptStatusType = "CREATED" | "STARTED" | "SUBMITTED";
export type Difficulty = "easy" | "medium" | "hard" | "mixed";

export interface QuizQuestion {
  id: string;
  prompt: string;
  options: string[]; // exactly 4, index 0..3
  difficulty: string;
  page?: number | null;
  source?: string | null;
  // Present only after grading (reveal_answers=true).
  correct_index?: number | null;
  correct_letter?: string | null;
  correct_answer?: string | null;
  explanation?: string | null;
  evidence?: string | null;
}

export interface Quiz {
  id: string;
  library_id: string;
  subject: string;
  title: string;
  difficulty: string;
  question_count: number;
  question_count_requested: number;
  time_limit_seconds: number;
  created_at: number;
  status: GenerationStatus;
  partial_reason: string;
  questions: QuizQuestion[];
}

export interface QuizAttempt {
  id: string;
  quiz_id: string;
  status: AttemptStatusType;
  created_at: number;
  started_at?: number | null;
  submitted_at?: number | null;
  answers: Record<string, string | null>;
  timed_out: boolean;
  score: number;
  total: number;
  correct: Record<string, boolean>;
  result_status: string;
  partial_reason: string;
}

export interface QuizScoreSummary {
  score: number;
  total: number;
  answered: number;
  correct?: Record<string, boolean>;
  unanswered?: string[];
  result_status?: string;
  partial_reason?: string;
  timed_out?: boolean;
  elapsed_seconds?: number | null;
  submitted_at?: number;
}

// Response from start_quiz: public quiz payload + attempt meta.
export interface QuizStartResponse extends Quiz {
  attempt_id: string;
  started_at?: number | null;
}

// Response from submit + result: graded quiz + attempt + score.
export interface QuizResultResponse {
  quiz: Quiz;
  attempt: QuizAttempt;
  result: string;
  score: QuizScoreSummary;
}

export interface CreateQuizInput {
  library: string;
  question_count?: number;
  difficulty?: Difficulty;
  topic?: string;
  time_limit_seconds?: number;
}
