import type { OrchestratorEventMessage } from "./protocol";

export interface SessionSnapshot {
  snapshotVersion?: number;
  sessionId?: string;
  taskId?: string;
  nodeId?: string;
  runner?: string;
  workspace?: string;
  task?: string;
  goal?: string;
  status?: string;
  phase?: string;
  stopReason?: string;
  error?: string;
  activeWorker?: string;
  activeSessionMode?: string;
  activeWorkerProfile?: string;
  activeWorkerTaskId?: string;
  activeWorkerCanInterrupt?: boolean;
  latestSummary?: string;
  lastProgressMessage?: string;
  latestArtifactSummary?: string;
  permissionSummary?: string;
  sessionInfoSummary?: string;
  mcpStatusSummary?: string;
  awaitingInput?: boolean;
  pendingUserPrompt?: string;
  pendingFollowups?: Array<Record<string, unknown>>;
  artifacts?: string[];
  recentHookEvents?: Array<Record<string, unknown>>;
  createdAt?: string;
  updatedAt?: string;
}

export interface UiSession {
  sessionId: string;
  task: string;
  displayTitle?: string;
  runner: string;
  status: string;
  phase: string;
  latestSummary: string;
  activeWorker: string;
  updatedAt: string;
  snapshot?: SessionSnapshot;
}

export interface TimelineEvent {
  id: string;
  seq?: number;
  kind: "phase" | "substep" | "summary" | "worker" | "snapshot" | "error" | "event";
  title: string;
  event?: string;
  status: string;
  detail: string;
  createdAt: string;
}

export interface TraceEntry {
  seq: number;
  timestamp: string;
  event: string;
  runner?: string;
  payload: Record<string, unknown>;
}

export interface SessionErrorItem {
  seq: number;
  errorLayer: string;
  errorCode: string;
  message: string;
  details: Record<string, unknown>;
  retryable: boolean;
  phase: string;
  worker: string;
  createdAt: string;
}

export interface ArtifactTile {
  path: string;
  changeType: string;
  summary: string;
  size?: number | null;
}

export interface SessionArtifactItem {
  path: string;
  changeType: string;
  size?: number | null;
  summary: string;
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
