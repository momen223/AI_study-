import type {
  ChatResponse,
  CreateQuizInput,
  Library,
  Quiz,
  QuizResultResponse,
  QuizStartResponse,
  UploadDoc,
} from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new Error("Cannot reach the API server. Make sure the Flask backend is running on port 5001.");
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.error) message = body.error;
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }
  return (await res.json()) as T;
}

export async function getLibraries(): Promise<Library[]> {
  const data = await request<{ libraries: Library[] }>("/api/libraries");
  return data.libraries;
}

export interface ChatBody {
  question: string;
  history: string;
  library?: string;
}

export async function chat(body: ChatBody): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function listDocuments(): Promise<UploadDoc[]> {
  const data = await request<{ documents: UploadDoc[] }>("/api/documents");
  return data.documents;
}

export async function uploadDocument(file: File): Promise<UploadDoc> {
  const form = new FormData();
  form.append("file", file);
  const data = await request<UploadDoc>("/api/documents/upload", {
    method: "POST",
    body: form,
  });
  return data;
}

export async function processDocument(id: string): Promise<{ status: string; chunks: number }> {
  return request("/api/documents/process", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id }),
  });
}

export async function deleteDocument(id: string): Promise<void> {
  await request(`/api/documents/${encodeURIComponent(id)}`, { method: "DELETE" });
}

/* -------------------------------------------------------------
   Quiz API — thin wrappers over the existing /api/quizzes/* routes.
   ------------------------------------------------------------- */

export async function createQuiz(input: CreateQuizInput): Promise<Quiz> {
  const data = await request<{ quiz: Quiz }>("/api/quizzes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      library: input.library,
      question_count: input.question_count,
      difficulty: input.difficulty,
      topic: input.topic,
      time_limit_seconds: input.time_limit_seconds,
    }),
  });
  return data.quiz;
}

export async function getQuiz(quizId: string): Promise<Quiz> {
  const data = await request<{ quiz: Quiz }>(
    `/api/quizzes/${encodeURIComponent(quizId)}`
  );
  return data.quiz;
}

export async function startQuiz(quizId: string): Promise<QuizStartResponse> {
  return request<QuizStartResponse>(
    `/api/quizzes/${encodeURIComponent(quizId)}/start`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    }
  );
}

export async function submitQuiz(
  quizId: string,
  attemptId: string,
  answers: Record<string, string>
): Promise<QuizResultResponse> {
  return request<QuizResultResponse>(
    `/api/quizzes/${encodeURIComponent(quizId)}/submit`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ attempt_id: attemptId, answers }),
    }
  );
}

export async function getQuizResult(
  quizId: string,
  attemptId: string
): Promise<QuizResultResponse> {
  return request<QuizResultResponse>(
    `/api/quizzes/${encodeURIComponent(quizId)}/result?attempt_id=${encodeURIComponent(
      attemptId
    )}`
  );
}

export async function deleteQuiz(quizId: string): Promise<void> {
  await request(`/api/quizzes/${encodeURIComponent(quizId)}`, {
    method: "DELETE",
  });
}

export async function getHealth(): Promise<{ status: string; service: string }> {
  return request<{ status: string; service: string }>("/api/health");
}
