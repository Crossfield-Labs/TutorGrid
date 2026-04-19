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
  params: Record<string, never>;
}
