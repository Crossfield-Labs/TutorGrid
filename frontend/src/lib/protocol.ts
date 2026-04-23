export interface OrchestratorEventMessage {
  type: "event";
  event: string;
  taskId: string | null;
  nodeId: string | null;
  sessionId: string | null;
  payload: Record<string, unknown>;
}

export interface SessionStartRequest {
  type: "req";
  id: string;
  method: "orchestrator.session.start";
  taskId: string;
  nodeId: string;
  params: {
    runner: string;
    workspace: string;
    task: string;
    goal?: string;
  };
}

export interface SessionInputRequest {
  type: "req";
  id: string;
  method: "orchestrator.session.input";
  sessionId: string;
  params: {
    text: string;
    inputIntent: "reply" | "redirect" | "instruction" | "explain" | "interrupt";
    target?: string;
  };
}

export interface SessionListRequest {
  type: "req";
  id: string;
  method: "orchestrator.session.list";
  params: {
    limit?: number;
    cursor?: string;
  };
}

export interface SessionHistoryRequest {
  type: "req";
  id: string;
  method: "orchestrator.session.history";
  sessionId: string;
  params: {
    limit?: number;
    cursor?: string;
  };
}

export interface SessionSnapshotRequest {
  type: "req";
  id: string;
  method: "orchestrator.session.snapshot";
  sessionId: string;
  params: Record<string, never>;
}

export interface SessionTraceRequest {
  type: "req";
  id: string;
  method: "orchestrator.session.trace";
  sessionId: string;
  params: {
    limit?: number;
  };
}

export interface SessionErrorsRequest {
  type: "req";
  id: string;
  method: "orchestrator.session.errors";
  sessionId: string;
  params: {
    limit?: number;
  };
}

export interface SessionArtifactsRequest {
  type: "req";
  id: string;
  method: "orchestrator.session.artifacts";
  sessionId: string;
  params: {
    limit?: number;
  };
}

export interface MemoryCleanupRequest {
  type: "req";
  id: string;
  method: "orchestrator.memory.cleanup";
  params: Record<string, never>;
}
