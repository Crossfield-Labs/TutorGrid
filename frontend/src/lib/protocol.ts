export interface OrchestratorEventMessage {
  type: "event";
  event: string;
  taskId: string | null;
  nodeId: string | null;
  sessionId: string | null;
  seq?: number;
  timestamp: string;
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

export interface MemoryReindexRequest {
  type: "req";
  id: string;
  method: "orchestrator.memory.reindex";
  params: Record<string, never>;
}

export interface MemorySearchRequest {
  type: "req";
  id: string;
  method: "orchestrator.memory.search";
  sessionId?: string;
  params: {
    text: string;
    limit?: number;
  };
}

export interface KnowledgeCourseCreateRequest {
  type: "req";
  id: string;
  method: "orchestrator.knowledge.course.create";
  params: {
    courseName: string;
    courseDescription?: string;
  };
}

export interface KnowledgeCourseListRequest {
  type: "req";
  id: string;
  method: "orchestrator.knowledge.course.list";
  params: {
    limit?: number;
  };
}

export interface KnowledgeCourseDeleteRequest {
  type: "req";
  id: string;
  method: "orchestrator.knowledge.course.delete";
  params: {
    courseId?: string;
    target?: string;
    text?: string;
  };
}

export interface KnowledgeFileIngestRequest {
  type: "req";
  id: string;
  method: "orchestrator.knowledge.file.ingest";
  params: {
    courseId: string;
    filePath: string;
    fileName?: string;
    chunkSize?: number;
  };
}

export interface KnowledgeFileListRequest {
  type: "req";
  id: string;
  method: "orchestrator.knowledge.file.list";
  params: {
    courseId: string;
    limit?: number;
  };
}

export interface KnowledgeFileDeleteRequest {
  type: "req";
  id: string;
  method: "orchestrator.knowledge.file.delete";
  params: {
    courseId: string;
    target?: string;
    text?: string;
  };
}

export interface KnowledgeChunkListRequest {
  type: "req";
  id: string;
  method: "orchestrator.knowledge.chunk.list";
  params: {
    courseId: string;
    limit?: number;
    text?: string;
  };
}

export interface KnowledgeJobListRequest {
  type: "req";
  id: string;
  method: "orchestrator.knowledge.job.list";
  params: {
    courseId: string;
    limit?: number;
  };
}

export interface KnowledgeRagQueryRequest {
  type: "req";
  id: string;
  method: "orchestrator.knowledge.rag.query";
  params: {
    courseId: string;
    text: string;
    limit?: number;
  };
}

export interface KnowledgeCourseReembedRequest {
  type: "req";
  id: string;
  method: "orchestrator.knowledge.course.reembed";
  params: {
    courseId?: string;
    target?: string;
    text?: string;
    batchSize?: number;
  };
}

export interface KnowledgeCourseReindexRequest {
  type: "req";
  id: string;
  method: "orchestrator.knowledge.course.reindex";
  params: {
    courseId?: string;
    target?: string;
    text?: string;
  };
}
