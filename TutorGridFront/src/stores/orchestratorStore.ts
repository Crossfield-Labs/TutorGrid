import { defineStore } from "pinia";

export type WsStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";

export interface OrchestratorEvent {
  event: string;
  taskId?: string | null;
  nodeId?: string | null;
  sessionId?: string | null;
  payload?: any;
  timestamp?: string;
  seq?: number;
}

export type SessionEventHandler = (event: string, payload: any) => void;

interface EventWaiter {
  eventName: string;
  resolve: (payload: any) => void;
  reject: (err: Error) => void;
  timer: ReturnType<typeof setTimeout>;
  sessionFilter?: string;
}

interface MessageClaim {
  resolve: (messageId: string) => void;
  reject: (err: Error) => void;
}

interface BufferedEvent {
  event: string;
  payload: any;
  ts: number;
}

const DEFAULT_WS_URL = "ws://127.0.0.1:3210/ws/orchestrator";
const REQUEST_TIMEOUT_MS = 60_000;
const RECONNECT_INITIAL_MS = 1_500;
const RECONNECT_MAX_MS = 15_000;
const CLAIM_TIMEOUT_MS = 30_000;
const SESSION_BUFFER_MS = 60_000;
const SESSION_BUFFER_MAX = 200;
const DEBUG = true;

let nextRequestId = 1;
function genRequestId(): string {
  return `req_${Date.now().toString(36)}_${nextRequestId++}`;
}

interface InternalState {
  ws: WebSocket | null;
  waiters: Map<string, EventWaiter[]>;
  sessionSubscribers: Map<string, Set<SessionEventHandler>>;
  messageClaims: Map<string, MessageClaim[]>;
  sessionBuffer: Map<string, BufferedEvent[]>;
  reconnectTimer: ReturnType<typeof setTimeout> | null;
  reconnectDelay: number;
  manualClose: boolean;
}

const internal: InternalState = {
  ws: null,
  waiters: new Map(),
  sessionSubscribers: new Map(),
  messageClaims: new Map(),
  sessionBuffer: new Map(),
  reconnectTimer: null,
  reconnectDelay: RECONNECT_INITIAL_MS,
  manualClose: false,
};

function pruneBuffer(arr: BufferedEvent[]) {
  const now = Date.now();
  while (arr.length > 0 && now - arr[0].ts > SESSION_BUFFER_MS) {
    arr.shift();
  }
  while (arr.length > SESSION_BUFFER_MAX) {
    arr.shift();
  }
}

function rejectAllPending(reason: string) {
  internal.waiters.forEach((arr) =>
    arr.forEach((w) => {
      clearTimeout(w.timer);
      w.reject(new Error(reason));
    })
  );
  internal.waiters.clear();
  internal.messageClaims.forEach((claims) =>
    claims.forEach((c) => c.reject(new Error(reason)))
  );
  internal.messageClaims.clear();
}

export const useOrchestratorStore = defineStore("orchestrator", {
  state: () => ({
    wsUrl: DEFAULT_WS_URL,
    status: "idle" as WsStatus,
    lastError: "" as string,
    sessions: [] as string[],
  }),

  getters: {
    isLive(state): boolean {
      return state.status === "connected";
    },
  },

  actions: {
    setWsUrl(url: string) {
      this.wsUrl = url;
    },

    connect(): Promise<void> {
      if (internal.ws && internal.ws.readyState === WebSocket.OPEN) {
        return Promise.resolve();
      }
      if (internal.ws && internal.ws.readyState === WebSocket.CONNECTING) {
        return new Promise((resolve, reject) => {
          const ws = internal.ws!;
          ws.addEventListener("open", () => resolve(), { once: true });
          ws.addEventListener(
            "error",
            () => reject(new Error("WebSocket error")),
            { once: true }
          );
        });
      }
      internal.manualClose = false;
      this.status = "connecting";
      this.lastError = "";
      return new Promise((resolve, reject) => {
        let ws: WebSocket;
        try {
          ws = new WebSocket(this.wsUrl);
        } catch (e) {
          this.status = "error";
          this.lastError = String(e);
          reject(e);
          return;
        }
        internal.ws = ws;
        const onOpen = () => {
          this.status = "connected";
          this.lastError = "";
          internal.reconnectDelay = RECONNECT_INITIAL_MS;
          ws.removeEventListener("error", onErrorOnce);
          resolve();
        };
        const onErrorOnce = () => {
          this.status = "error";
          this.lastError = "WebSocket connect failed";
          ws.removeEventListener("open", onOpen);
          reject(new Error(this.lastError));
        };
        ws.addEventListener("open", onOpen, { once: true });
        ws.addEventListener("error", onErrorOnce, { once: true });
        ws.addEventListener("message", (ev) => this._onMessage(ev));
        ws.addEventListener("close", () => this._onClose());
      });
    },

    disconnect() {
      internal.manualClose = true;
      if (internal.reconnectTimer) {
        clearTimeout(internal.reconnectTimer);
        internal.reconnectTimer = null;
      }
      if (internal.ws) {
        try {
          internal.ws.close();
        } catch {
          /* ignore */
        }
        internal.ws = null;
      }
      this.status = "idle";
      rejectAllPending("WebSocket disconnected");
    },

    _scheduleReconnect() {
      if (internal.manualClose) return;
      if (internal.reconnectTimer) return;
      const delay = internal.reconnectDelay;
      internal.reconnectTimer = setTimeout(() => {
        internal.reconnectTimer = null;
        internal.reconnectDelay = Math.min(delay * 2, RECONNECT_MAX_MS);
        this.connect().catch(() => this._scheduleReconnect());
      }, delay);
    },

    _onClose() {
      this.status = "disconnected";
      rejectAllPending("WebSocket closed");
      if (!internal.manualClose) {
        this._scheduleReconnect();
      }
    },

    _onMessage(ev: MessageEvent) {
      let frame: any;
      try {
        frame = JSON.parse(ev.data as string);
      } catch {
        return;
      }
      if (frame?.type !== "event") return;
      const orchEvent = frame as OrchestratorEvent;
      this._dispatchEvent(orchEvent);
    },

    _dispatchEvent(frame: OrchestratorEvent) {
      const sessionId = frame.sessionId || frame.payload?.sessionId || "";
      if (DEBUG) {
        // eslint-disable-next-line no-console
        console.debug(
          `[orch] ← ${frame.event}`,
          sessionId ? `sid=${sessionId.slice(0, 8)}` : "",
          frame.payload
        );
      }

      // 0. buffer per-session events for late subscribers
      if (sessionId) {
        let buf = internal.sessionBuffer.get(sessionId);
        if (!buf) {
          buf = [];
          internal.sessionBuffer.set(sessionId, buf);
        }
        buf.push({ event: frame.event, payload: frame.payload, ts: Date.now() });
        pruneBuffer(buf);
      }

      // 1. session subscribers
      if (sessionId) {
        const subs = internal.sessionSubscribers.get(sessionId);
        if (subs) {
          subs.forEach((h) => {
            try {
              h(frame.event, frame.payload);
            } catch (e) {
              console.error("[orchestrator] subscriber threw", e);
            }
          });
        }
      }

      // 2. message.started → resolve a pending message claim for this session
      if (frame.event === "orchestrator.session.message.started" && sessionId) {
        const claims = internal.messageClaims.get(sessionId);
        if (claims && claims.length > 0) {
          const claim = claims.shift()!;
          claim.resolve(frame.payload?.messageId || "");
        }
      }

      // 3. request waiters keyed by event name
      const waiters = internal.waiters.get(frame.event);
      if (waiters && waiters.length > 0) {
        const idx = waiters.findIndex(
          (w) => !w.sessionFilter || w.sessionFilter === sessionId
        );
        if (idx >= 0) {
          const w = waiters[idx];
          waiters.splice(idx, 1);
          if (waiters.length === 0) internal.waiters.delete(frame.event);
          clearTimeout(w.timer);
          w.resolve(frame.payload);
        }
      }
    },

    request<T = any>(
      method: string,
      params: any = {},
      opts: {
        sessionId?: string;
        taskId?: string;
        nodeId?: string;
        timeoutMs?: number;
        expectEventName?: string;
        scopeBySession?: boolean;
      } = {}
    ): Promise<T> {
      return new Promise<T>((resolve, reject) => {
        if (!internal.ws || internal.ws.readyState !== WebSocket.OPEN) {
          reject(new Error("WebSocket not connected"));
          return;
        }
        const id = genRequestId();
        const expectedEvent = opts.expectEventName || method;
        const timer = setTimeout(() => {
          const arr = internal.waiters.get(expectedEvent);
          if (arr) {
            const i = arr.findIndex((w) => w.timer === timer);
            if (i >= 0) {
              arr.splice(i, 1);
              if (arr.length === 0) internal.waiters.delete(expectedEvent);
            }
          }
          reject(new Error(`Request ${method} timed out`));
        }, opts.timeoutMs ?? REQUEST_TIMEOUT_MS);

        const waiter: EventWaiter = {
          eventName: expectedEvent,
          resolve,
          reject,
          timer,
          sessionFilter:
            opts.scopeBySession && opts.sessionId ? opts.sessionId : undefined,
        };
        let arr = internal.waiters.get(expectedEvent);
        if (!arr) {
          arr = [];
          internal.waiters.set(expectedEvent, arr);
        }
        arr.push(waiter);

        const frame: any = {
          type: "req",
          id,
          method,
          params: params || {},
        };
        if (opts.sessionId) frame.sessionId = opts.sessionId;
        if (opts.taskId) frame.taskId = opts.taskId;
        if (opts.nodeId) frame.nodeId = opts.nodeId;

        try {
          internal.ws.send(JSON.stringify(frame));
        } catch (e) {
          clearTimeout(timer);
          const i = arr.indexOf(waiter);
          if (i >= 0) arr.splice(i, 1);
          reject(e as Error);
        }
      });
    },

    subscribeSession(
      sessionId: string,
      handler: SessionEventHandler,
      opts: { replayBuffered?: boolean } = { replayBuffered: true }
    ): () => void {
      if (!sessionId) return () => undefined;
      let set = internal.sessionSubscribers.get(sessionId);
      if (!set) {
        set = new Set();
        internal.sessionSubscribers.set(sessionId, set);
      }
      set.add(handler);
      if (!this.sessions.includes(sessionId)) this.sessions.push(sessionId);
      if (opts.replayBuffered !== false) {
        const buf = internal.sessionBuffer.get(sessionId);
        if (buf && buf.length > 0) {
          if (DEBUG) {
            // eslint-disable-next-line no-console
            console.debug(
              `[orch] replay ${buf.length} buffered events for sid=${sessionId.slice(0, 8)}`
            );
          }
          [...buf].forEach((b) => {
            try {
              handler(b.event, b.payload);
            } catch (e) {
              console.error("[orchestrator] replay handler threw", e);
            }
          });
        }
      }
      return () => {
        const s = internal.sessionSubscribers.get(sessionId);
        if (!s) return;
        s.delete(handler);
        if (s.size === 0) internal.sessionSubscribers.delete(sessionId);
      };
    },

    claimNextMessageId(sessionId: string): Promise<string> {
      return new Promise((resolve, reject) => {
        const claim: MessageClaim = {
          resolve: (mid) => {
            clearTimeout(timer);
            resolve(mid);
          },
          reject: (err) => {
            clearTimeout(timer);
            reject(err);
          },
        };
        const timer = setTimeout(() => {
          const claims = internal.messageClaims.get(sessionId) || [];
          const idx = claims.indexOf(claim);
          if (idx >= 0) claims.splice(idx, 1);
          reject(
            new Error(`message.started not received within ${CLAIM_TIMEOUT_MS}ms`)
          );
        }, CLAIM_TIMEOUT_MS);
        let claims = internal.messageClaims.get(sessionId);
        if (!claims) {
          claims = [];
          internal.messageClaims.set(sessionId, claims);
        }
        claims.push(claim);
      });
    },

    async runTipTapCommand(opts: {
      command: string;
      selectionText: string;
      documentText?: string;
      text?: string;
      target?: string;
      sessionId?: string;
      workspace?: string;
      runner?: string;
      taskId?: string;
      nodeId?: string;
    }): Promise<{
      sessionId: string;
      mode: "preview" | "start" | "followup";
      isNew: boolean;
    }> {
      const params: any = {
        commandName: opts.command,
        selectionText: opts.selectionText || "",
        documentText: opts.documentText || "",
        execute: true,
      };
      if (opts.text) params.text = opts.text;
      if (opts.target) params.target = opts.target;
      if (opts.workspace) params.workspace = opts.workspace;
      if (opts.runner) params.runner = opts.runner;

      const payload = await this.request<any>(
        "orchestrator.tiptap.command",
        params,
        {
          sessionId: opts.sessionId,
          taskId: opts.taskId,
          nodeId: opts.nodeId,
        }
      );
      const sessionId = payload?.sessionId || opts.sessionId || "";
      const mode = (payload?.mode || "start") as "preview" | "start" | "followup";
      const isNew = mode === "start";
      return { sessionId, mode, isNew };
    },

    sessionInput(opts: {
      sessionId: string;
      intent:
        | "reply"
        | "redirect"
        | "instruction"
        | "comment"
        | "explain"
        | "interrupt";
      text: string;
      target?: string;
    }): Promise<any> {
      return this.request<any>(
        "orchestrator.session.input",
        {
          inputIntent: opts.intent,
          text: opts.text,
          ...(opts.target ? { target: opts.target } : {}),
        },
        {
          sessionId: opts.sessionId,
          expectEventName: "orchestrator.session.followup.accepted",
        }
      );
    },

    knowledgeCourseList(opts: { limit?: number } = {}): Promise<any> {
      return this.request<any>(
        "orchestrator.knowledge.course.list",
        { limit: opts.limit ?? 50 },
        { expectEventName: "orchestrator.knowledge.course.list" }
      );
    },

    knowledgeCourseCreate(opts: {
      courseName: string;
      courseDescription?: string;
    }): Promise<any> {
      return this.request<any>(
        "orchestrator.knowledge.course.create",
        {
          courseName: opts.courseName,
          courseDescription: opts.courseDescription || "",
        },
        { expectEventName: "orchestrator.knowledge.course.create" }
      );
    },

    knowledgeFileList(opts: {
      courseId: string;
      limit?: number;
    }): Promise<any> {
      return this.request<any>(
        "orchestrator.knowledge.file.list",
        { courseId: opts.courseId, limit: opts.limit ?? 200 },
        { expectEventName: "orchestrator.knowledge.file.list" }
      );
    },

    knowledgeFileIngest(opts: {
      courseId: string;
      filePath: string;
      fileName?: string;
      chunkSize?: number;
    }): Promise<any> {
      return this.request<any>(
        "orchestrator.knowledge.file.ingest",
        {
          courseId: opts.courseId,
          filePath: opts.filePath,
          fileName: opts.fileName || "",
          chunkSize: opts.chunkSize || 900,
        },
        {
          expectEventName: "orchestrator.knowledge.file.ingest",
          timeoutMs: 180_000,
        }
      );
    },

    knowledgeRagQuery(opts: {
      courseId: string;
      text: string;
      limit?: number;
    }): Promise<any> {
      return this.request<any>(
        "orchestrator.knowledge.rag.query",
        {
          courseId: opts.courseId,
          text: opts.text,
          limit: opts.limit ?? 8,
        },
        {
          expectEventName: "orchestrator.knowledge.rag.query",
          timeoutMs: 90_000,
        }
      );
    },

    fetchSessionArtifacts(sessionId: string): Promise<any> {
      return this.request<any>(
        "orchestrator.session.artifacts",
        {},
        {
          sessionId,
          scopeBySession: true,
          expectEventName: "orchestrator.session.artifacts",
        }
      );
    },

    fetchSessionSnapshot(sessionId: string): Promise<any> {
      return this.request<any>(
        "orchestrator.session.snapshot",
        {},
        {
          sessionId,
          scopeBySession: true,
          expectEventName: "orchestrator.session.snapshot",
        }
      );
    },

    createTask(opts: {
      instruction: string;
      docId: string;
      workspace?: string;
      runner?: string;
    }): Promise<any> {
      return this.request<any>(
        "orchestrator.task.create",
        {
          runner: opts.runner || "orchestrator",
          workspace: opts.workspace || ".",
          instruction: opts.instruction,
          docId: opts.docId,
        },
        {
          taskId: `task_${Date.now()}`,
          nodeId: "doc_task",
          expectEventName: "orchestrator.task.create",
        }
      );
    },

    resumeTask(opts: { taskId: string; sessionId: string; content: string }): Promise<any> {
      return this.request<any>(
        "orchestrator.task.resume",
        {
          sessionId: opts.sessionId,
          kind: "reply",
          content: opts.content,
        },
        {
          sessionId: opts.sessionId,
          taskId: opts.taskId,
          expectEventName: "orchestrator.session.followup.accepted",
        }
      );
    },

    interruptTask(opts: { taskId: string; sessionId: string; text?: string }): Promise<any> {
      return this.request<any>(
        "orchestrator.task.interrupt",
        {
          sessionId: opts.sessionId,
          text: opts.text || "Interrupt requested.",
        },
        {
          sessionId: opts.sessionId,
          taskId: opts.taskId,
          expectEventName: "orchestrator.session.followup.accepted",
        }
      );
    },

    applyDocWrite(opts: { taskId: string; sessionId: string; writeId: string }): Promise<any> {
      return this.request<any>(
        "orchestrator.task.apply_doc_write",
        {
          sessionId: opts.sessionId,
          writeId: opts.writeId,
        },
        {
          sessionId: opts.sessionId,
          taskId: opts.taskId,
          expectEventName: "orchestrator.task.apply_doc_write",
        }
      );
    },
  },
});
