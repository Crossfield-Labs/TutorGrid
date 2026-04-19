import type { OrchestratorEventMessage } from "./protocol";

export interface UiSession {
  sessionId: string;
  task: string;
  runner: string;
  status: string;
  phase: string;
  latestSummary: string;
  activeWorker: string;
  updatedAt: string;
}

export interface TimelineEvent {
  id: string;
  kind: "phase" | "substep" | "summary" | "worker" | "snapshot" | "error" | "event";
  title: string;
  status: string;
  detail: string;
  createdAt: string;
}

interface ClientOptions {
  url: string;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: () => void;
  onEvent?: (message: OrchestratorEventMessage) => void;
}

export function buildWsUrl() {
  return "ws://127.0.0.1:3210/ws/orchestrator";
}

export function createClient(options: ClientOptions) {
  let socket: WebSocket | null = null;

  return {
    connect() {
      socket = new WebSocket(options.url);
      socket.addEventListener("open", () => options.onOpen?.());
      socket.addEventListener("close", () => options.onClose?.());
      socket.addEventListener("error", () => options.onError?.());
      socket.addEventListener("message", (event) => {
        try {
          const message = JSON.parse(String(event.data)) as OrchestratorEventMessage;
          options.onEvent?.(message);
        } catch {
          options.onError?.();
        }
      });
    },
    close() {
      socket?.close();
    },
    send(payload: object) {
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        return false;
      }
      socket.send(JSON.stringify(payload));
      return true;
    },
  };
}
