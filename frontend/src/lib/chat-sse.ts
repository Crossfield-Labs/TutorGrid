export type ChatSseEvent =
  | { type: "start"; message_id?: string }
  | { type: "tool_call"; tool?: string; query?: string; [key: string]: unknown }
  | { type: "tool_result"; tool?: string; citations?: ChatCitation[]; results?: unknown[]; [key: string]: unknown }
  | { type: "delta"; content?: string }
  | { type: "done"; message_id?: string; metadata?: Record<string, unknown> }
  | { type: "error"; message?: string; [key: string]: unknown };

export type ChatCitation = {
  source?: string;
  page?: number;
  chunk?: string;
  score?: number;
};

export type ChatStreamRequest = {
  session_id: string;
  message: string;
  course_id?: string;
  tools?: string[];
  context?: {
    doc_id?: string;
    recent_paragraphs?: string[];
  };
};

export type ChatStreamHandlers = {
  onEvent: (event: ChatSseEvent) => void;
  signal?: AbortSignal;
};

export async function streamChat(
  baseUrl: string,
  payload: ChatStreamRequest,
  handlers: ChatStreamHandlers,
) {
  const response = await fetch(`${normalizeBaseUrl(baseUrl)}/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal: handlers.signal,
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(detail || `HTTP ${response.status}`);
  }
  if (!response.body) {
    throw new Error("The browser did not expose a readable response body.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const event = parseSseFrame(frame);
      if (event) {
        handlers.onEvent(event);
      }
    }
  }

  const tail = buffer.trim();
  if (tail) {
    const event = parseSseFrame(tail);
    if (event) {
      handlers.onEvent(event);
    }
  }
}

function parseSseFrame(frame: string): ChatSseEvent | null {
  const dataLines = frame
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart());
  if (!dataLines.length) {
    return null;
  }
  try {
    const payload = JSON.parse(dataLines.join("\n")) as ChatSseEvent;
    return typeof payload?.type === "string" ? payload : null;
  } catch {
    return { type: "error", message: dataLines.join("\n") };
  }
}

function normalizeBaseUrl(value: string) {
  return (value.trim() || "http://127.0.0.1:8000").replace(/\/+$/, "");
}
