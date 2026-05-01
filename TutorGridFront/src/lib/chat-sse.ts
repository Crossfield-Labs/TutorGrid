/**
 * Chat SSE 客户端
 *
 * 后端协议见 backend/server/chat_api.py:
 *   data: {"type":"start","message_id":"..."}
 *   data: {"type":"tool_call","tool":"rag","query":"..."}
 *   data: {"type":"tool_result","tool":"rag","citations":[...]}
 *   data: {"type":"delta","content":"..."}
 *   data: {"type":"done","message_id":"...","metadata":{...}}
 *   data: {"type":"error","message":"..."}
 */

export interface ChatStartEvent {
  type: "start";
  message_id: string;
}
export interface ChatDeltaEvent {
  type: "delta";
  content: string;
}
export interface ChatToolCallEvent {
  type: "tool_call";
  tool: string;
  query?: string;
}
export interface ChatCitation {
  source?: string;
  page?: number;
  chunk?: string;
  score?: number;
  fileId?: string;
  fileName?: string;
  chunkId?: string;
  content?: string;
}
export interface ChatToolResultEvent {
  type: "tool_result";
  tool: string;
  citations?: ChatCitation[];
  results?: Array<{ title?: string; url?: string; content?: string; score?: number }>;
  warning?: string;
  fallback?: string;
}
export interface ChatDoneEvent {
  type: "done";
  message_id: string;
  metadata?: { tools_called?: string[]; tokens_used?: number };
}
export interface ChatErrorEvent {
  type: "error";
  message: string;
}

export type ChatSSEEvent =
  | ChatStartEvent
  | ChatDeltaEvent
  | ChatToolCallEvent
  | ChatToolResultEvent
  | ChatDoneEvent
  | ChatErrorEvent;

export interface ChatStreamRequest {
  session_id: string;
  message: string;
  course_id?: string;
  tools?: string[];
  context?: {
    doc_id?: string;
    recent_paragraphs?: string[];
  };
}

export interface ChatSSEOptions {
  endpoint?: string;
  payload: ChatStreamRequest;
  onEvent: (event: ChatSSEEvent) => void;
  signal?: AbortSignal;
}

export const DEFAULT_CHAT_SSE_ENDPOINT = "http://127.0.0.1:8000/api/chat/stream";

/**
 * 消费 Chat SSE 流。返回的 Promise 在 'done' / 'error' 事件后 resolve。
 * 调用方负责构造 onEvent 回调里的状态更新（写入 messageStore 等）。
 */
export async function streamChat(options: ChatSSEOptions): Promise<void> {
  const endpoint = options.endpoint ?? DEFAULT_CHAT_SSE_ENDPOINT;
  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options.payload),
    signal: options.signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`Chat SSE 请求失败：${res.status} ${res.statusText}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE 帧之间用空行 (\n\n) 分隔
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const dataLine = frame
          .split("\n")
          .find((line) => line.startsWith("data: "));
        if (!dataLine) continue;
        const json = dataLine.slice(6).trim();
        if (!json) continue;
        try {
          const event = JSON.parse(json) as ChatSSEEvent;
          options.onEvent(event);
        } catch (e) {
          console.warn("[chat-sse] parse error", e, frame);
        }
      }
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      /* noop */
    }
  }
}
