import { defineStore } from "pinia";
import { useOrchestratorStore } from "@/stores/orchestratorStore";

export type TaskStepStatus =
  | "pending"
  | "running"
  | "done"
  | "failed"
  | "awaiting_user"
  | "interrupted";

export interface OrchestratorTaskStep {
  phase: string;
  name: string;
  status: TaskStepStatus;
  index: number;
}

export interface OrchestratorTaskItem {
  taskId: string;
  sessionId: string;
  docId: string;
  title: string;
  status: TaskStepStatus;
  phase: string;
  summary: string;
  currentStepIndex: number;
  stepTotal: number;
  resultSummary: string;
  awaitingUser: boolean;
  prompt: string;
  artifacts: Array<Record<string, unknown>>;
  steps: OrchestratorTaskStep[];
  updatedAt: string;
}

function defaultSteps(): OrchestratorTaskStep[] {
  return [
    { phase: "planning", name: "规划任务", status: "pending", index: 1 },
    { phase: "tools", name: "执行工具", status: "pending", index: 2 },
    { phase: "verify", name: "验证结果", status: "pending", index: 3 },
    { phase: "finalize", name: "整理输出", status: "pending", index: 4 },
  ];
}

export const useOrchestratorTaskStore = defineStore("orchestratorTask", {
  state: () => ({
    tasksById: {} as Record<string, OrchestratorTaskItem>,
    taskIdsByDoc: {} as Record<string, string[]>,
    activeTaskIdByDoc: {} as Record<string, string>,
    subscriptions: {} as Record<string, boolean>,
    starting: false,
    lastError: "",
  }),

  getters: {
    activeTaskForDoc: (state) => {
      return (docId: string) => {
        const taskId = state.activeTaskIdByDoc[docId] || "";
        return taskId ? state.tasksById[taskId] || null : null;
      };
    },
  },

  actions: {
    _upsertTask(task: OrchestratorTaskItem) {
      this.tasksById[task.taskId] = task;
      if (!task.docId) return;
      const existing = this.taskIdsByDoc[task.docId] || [];
      if (!existing.includes(task.taskId)) {
        this.taskIdsByDoc[task.docId] = [task.taskId, ...existing];
      }
      this.activeTaskIdByDoc[task.docId] = task.taskId;
    },

    _ensureSessionSubscription(sessionId: string) {
      if (!sessionId || this.subscriptions[sessionId]) return;
      const orchestrator = useOrchestratorStore();
      orchestrator.subscribeSession(sessionId, (event, payload) => {
        if (event === "orchestrator.task.step") {
          const taskId = String(payload?.task_id || "");
          if (!taskId) return;
          const previous = this.tasksById[taskId];
          const task: OrchestratorTaskItem = {
            taskId,
            sessionId: String(payload?.session_id || sessionId),
            docId: String(payload?.doc_id || previous?.docId || ""),
            title: previous?.title || "编排任务",
            status: payload?.status || "pending",
            phase: payload?.phase || "planning",
            summary: String(payload?.summary || ""),
            currentStepIndex: Number(payload?.step_index || 1),
            stepTotal: Number(payload?.step_total || 4),
            resultSummary: previous?.resultSummary || "",
            awaitingUser: Boolean(payload?.awaiting_user),
            prompt: previous?.prompt || "",
            artifacts: previous?.artifacts || [],
            steps:
              Array.isArray(payload?.steps) && payload.steps.length > 0
                ? payload.steps
                : defaultSteps(),
            updatedAt: new Date().toISOString(),
          };
          this._upsertTask(task);
          return;
        }

        if (event === "orchestrator.task.awaiting_user") {
          const taskId = String(payload?.task_id || "");
          const existing = this.tasksById[taskId];
          if (!existing) return;
          this._upsertTask({
            ...existing,
            status: "awaiting_user",
            awaitingUser: true,
            prompt: String(payload?.prompt || ""),
            updatedAt: new Date().toISOString(),
          });
          return;
        }

        if (event === "orchestrator.task.result") {
          const taskId = String(payload?.task_id || "");
          if (!taskId) return;
          const previous = this.tasksById[taskId];
          this._upsertTask({
            taskId,
            sessionId: String(payload?.session_id || sessionId),
            docId: String(payload?.doc_id || previous?.docId || ""),
            title: previous?.title || "编排任务",
            status: payload?.status || "done",
            phase: "finalize",
            summary: previous?.summary || "",
            currentStepIndex: 4,
            stepTotal: 4,
            resultSummary: String(payload?.content || ""),
            awaitingUser: false,
            prompt: "",
            artifacts: Array.isArray(payload?.artifacts) ? payload.artifacts : [],
            steps:
              previous?.steps?.length
                ? previous.steps.map((step) => ({ ...step, status: step.status === "failed" ? step.status : "done" }))
                : defaultSteps().map((step) => ({ ...step, status: "done" })),
            updatedAt: new Date().toISOString(),
          });
        }
      });
      this.subscriptions[sessionId] = true;
    },

    async createTask(opts: { docId: string; instruction: string; workspace?: string; runner?: string }) {
      const orchestrator = useOrchestratorStore();
      this.starting = true;
      this.lastError = "";
      try {
        await orchestrator.connect();
        const payload = await orchestrator.createTask({
          instruction: opts.instruction,
          docId: opts.docId,
          workspace: opts.workspace,
          runner: opts.runner,
        });
        const sessionId = String(payload?.session_id || "");
        const taskId = String(payload?.task_id || "");
        if (sessionId) {
          this._ensureSessionSubscription(sessionId);
        }
        if (taskId) {
          this._upsertTask({
            taskId,
            sessionId,
            docId: opts.docId,
            title: opts.instruction,
            status: "pending",
            phase: "planning",
            summary: "任务已创建，等待开始。",
            currentStepIndex: 1,
            stepTotal: 4,
            resultSummary: "",
            awaitingUser: false,
            prompt: "",
            artifacts: [],
            steps: defaultSteps(),
            updatedAt: new Date().toISOString(),
          });
        }
        return payload;
      } catch (error) {
        this.lastError = String((error as Error)?.message || error);
        throw error;
      } finally {
        this.starting = false;
      }
    },

    async resumeTask(taskId: string, content: string) {
      const orchestrator = useOrchestratorStore();
      const task = this.tasksById[taskId];
      if (!task) return;
      await orchestrator.connect();
      await orchestrator.resumeTask({
        taskId: task.taskId,
        sessionId: task.sessionId,
        content,
      });
    },

    async interruptTask(taskId: string) {
      const orchestrator = useOrchestratorStore();
      const task = this.tasksById[taskId];
      if (!task) return;
      await orchestrator.connect();
      await orchestrator.interruptTask({
        taskId: task.taskId,
        sessionId: task.sessionId,
      });
    },
  },
});
