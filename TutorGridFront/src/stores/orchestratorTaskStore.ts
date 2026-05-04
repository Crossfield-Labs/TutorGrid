import { defineStore } from "pinia";
import { useOrchestratorStore } from "@/stores/orchestratorStore";

export type TaskStepStatus =
  | "pending"
  | "running"
  | "done"
  | "failed"
  | "awaiting_user"
  | "interrupted";

export type OrchestratorNodeType = "plan" | "tool" | "doc_write" | "await_user";

export interface OrchestratorNode {
  id: string;
  type: OrchestratorNodeType;
  toolName?: string;
  status: TaskStepStatus;
  startedAt: number;
  endedAt?: number;
  durationMs?: number;
  argsPreview?: string;
  outputPreview?: string;
  workerSession?: { worker: string; sessionKey: string; mode: string };
  artifacts?: string[];
  // doc_write specific
  writeId?: string;
  writeKind?: string;
  writeTitle?: string;
  writeContent?: string;
  writePlacement?: string;
  writeApplied?: boolean;
}

export interface OrchestratorTaskStep {
  phase: string;
  name: string;
  status: TaskStepStatus;
  index: number;
  detail?: string;
}

/**
 * 计划步骤（plan step） —— LLM 通过 declare_plan tool 提前声明的高层意图。
 * 任务一开始就立刻在 TileGrid 渲染成 N 个 pending 磁贴；执行时随节点完成动态变状态。
 *
 * 与 raw OrchestratorNode 的区别：
 *  - PlanStep: 用户视角的工作单元 (2-5 个), 先声明后执行, 按 kind/sessionKey 关联节点
 *  - OrchestratorNode: 每个 tool call 一个原始节点, drawer 里看, 数量任意 (3-30+)
 */
export type OrchestratorPlanStepKind = "worker" | "doc_write" | "await_user" | "inspect";

export interface OrchestratorPlanStep {
  id: string;
  index: number;
  label: string;
  kind: OrchestratorPlanStepKind;
  brief: string;
  expectedWorker: string;
  expectedSessionKey: string;
  status: TaskStepStatus;
  nodeIds: string[];
  startedAt: number;
  endedAt: number;
  durationMs: number;
  declaredAt: number;
}

export interface OrchestratorPlan {
  planId: string;
  declaredAt: number;
  steps: OrchestratorPlanStep[];
}

export interface PendingDocWrite {
  writeId: string;
  taskId: string;
  sessionId: string;
  docId: string;
  kind: string;
  title: string;
  content: string;
  placement: string;
  citations: Array<Record<string, unknown>>;
  createdAt: number;
  applied: boolean;
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
  workerRuns: Array<Record<string, unknown>>;
  activeWorker: string;
  activeSessionMode: string;
  activeWorkerProfile: string;
  steps: OrchestratorTaskStep[];
  nodes: OrchestratorNode[];
  plan: OrchestratorPlan | null;
  pendingDocWrites: PendingDocWrite[];
  updatedAt: string;
}

function defaultSteps(): OrchestratorTaskStep[] {
  return [
    { phase: "planning", name: "规划任务", status: "pending", index: 1, detail: "" },
    { phase: "tools", name: "执行工具", status: "pending", index: 2, detail: "" },
    { phase: "verify", name: "验证结果", status: "pending", index: 3, detail: "" },
    { phase: "finalize", name: "整理输出", status: "pending", index: 4, detail: "" },
  ];
}

function mergeSteps(
  previousSteps: OrchestratorTaskStep[] | undefined,
  incomingSteps: Array<Record<string, unknown>> | undefined,
  currentPhase: string,
  currentDetail: string,
): OrchestratorTaskStep[] {
  const baseSteps = previousSteps?.length ? previousSteps.map((step) => ({ ...step })) : defaultSteps();
  const incomingByPhase = new Map(
    (Array.isArray(incomingSteps) ? incomingSteps : []).map((step) => [String(step.phase || ""), step]),
  );
  return baseSteps.map((step) => {
    const incoming = incomingByPhase.get(step.phase);
    const mergedStep: OrchestratorTaskStep = {
      ...step,
      name: String(incoming?.name || step.name),
      status: (incoming?.status as TaskStepStatus) || step.status,
      index: Number(incoming?.index || step.index),
      detail: step.detail || "",
    };
    if (step.phase === currentPhase && currentDetail.trim()) {
      mergedStep.detail = currentDetail;
    }
    return mergedStep;
  });
}

function emptyTask(taskId: string, sessionId: string, docId: string): OrchestratorTaskItem {
  return {
    taskId,
    sessionId,
    docId,
    title: "编排任务",
    status: "pending",
    phase: "planning",
    summary: "",
    currentStepIndex: 1,
    stepTotal: 4,
    resultSummary: "",
    awaitingUser: false,
    prompt: "",
    artifacts: [],
    workerRuns: [],
    activeWorker: "",
    activeSessionMode: "",
    activeWorkerProfile: "",
    steps: defaultSteps(),
    nodes: [],
    plan: null,
    pendingDocWrites: [],
    updatedAt: new Date().toISOString(),
  };
}

function normalizePlanStep(raw: Record<string, unknown>, idx: number): OrchestratorPlanStep {
  return {
    id: String(raw.id || `step_${idx + 1}`),
    index: Number(raw.index || idx + 1),
    label: String(raw.label || ""),
    kind: (String(raw.kind || "worker") as OrchestratorPlanStepKind),
    brief: String(raw.brief || ""),
    expectedWorker: String(raw.expected_worker || raw.expectedWorker || ""),
    expectedSessionKey: String(raw.expected_session_key || raw.expectedSessionKey || ""),
    status: (String(raw.status || "pending") as TaskStepStatus),
    nodeIds: Array.isArray(raw.node_ids) ? (raw.node_ids as string[]) : [],
    startedAt: Number(raw.started_at || 0),
    endedAt: Number(raw.ended_at || 0),
    durationMs: Number(raw.duration_ms || 0),
    declaredAt: Number(raw.declared_at || 0),
  };
}

/**
 * Match a raw node to one of the declared plan steps.
 *  - worker nodes (delegate_*) → match by sessionKey first, then by step.kind=worker
 *  - doc_write nodes → match next pending doc_write step (or oldest doc_write step)
 *  - await_user nodes → match next pending await_user step
 *
 * Returns the index of the matched step in plan.steps, or -1.
 */
function matchNodeToPlanStep(plan: OrchestratorPlan, node: OrchestratorNode): number {
  if (!plan.steps.length) return -1;
  if (node.type === "doc_write") {
    const exact = plan.steps.findIndex((s) => s.kind === "doc_write" && s.status !== "done");
    if (exact >= 0) return exact;
    return plan.steps.findIndex((s) => s.kind === "doc_write");
  }
  if (node.type === "await_user") {
    const exact = plan.steps.findIndex((s) => s.kind === "await_user" && s.status !== "done");
    if (exact >= 0) return exact;
    return plan.steps.findIndex((s) => s.kind === "await_user");
  }
  // tool / worker nodes
  const isDelegate = !!node.toolName && node.toolName.startsWith("delegate_");
  if (isDelegate) {
    const sessionKey = node.workerSession?.sessionKey || "";
    if (sessionKey) {
      const bySession = plan.steps.findIndex(
        (s) => s.kind === "worker" && s.expectedSessionKey === sessionKey,
      );
      if (bySession >= 0) return bySession;
    }
    const nextWorker = plan.steps.findIndex(
      (s) => s.kind === "worker" && s.status !== "done",
    );
    if (nextWorker >= 0) return nextWorker;
    return plan.steps.findIndex((s) => s.kind === "worker");
  }
  // light tool calls (read_file / list_files / glob / grep / run_shell / ...) —
  // attach to the currently-running worker step if any, otherwise to the first
  // pending step (so they're not orphaned but don't pollute "doc_write" steps).
  const running = plan.steps.findIndex((s) => s.status === "running");
  if (running >= 0) return running;
  return plan.steps.findIndex((s) => s.status === "pending");
}

function applyNodeToPlan(plan: OrchestratorPlan, node: OrchestratorNode): OrchestratorPlan {
  const idx = matchNodeToPlanStep(plan, node);
  if (idx < 0) return plan;
  const newSteps = plan.steps.map((step, i) => {
    if (i !== idx) return step;
    const nodeIds = step.nodeIds.includes(node.id) ? step.nodeIds : [...step.nodeIds, node.id];
    let { status, startedAt, endedAt, durationMs } = step;
    if (status === "pending") {
      status = "running";
      startedAt = node.startedAt || Date.now();
    }
    if (node.status === "running" && status !== "done" && status !== "failed") {
      status = "running";
    }
    if (node.status === "failed") {
      status = "failed";
      endedAt = node.endedAt || Date.now();
      durationMs = endedAt - (startedAt || endedAt);
    }
    if (node.status === "awaiting_user") {
      status = "awaiting_user";
    }
    if (node.status === "done") {
      // Mark this plan step done only if its kind is doc_write/await_user, OR
      // if it's a worker step and the node is a delegate_* node (lightweight
      // tools don't conclude a worker step).
      const finishesStep =
        step.kind === "doc_write" ||
        step.kind === "await_user" ||
        (step.kind === "worker" && !!node.toolName?.startsWith("delegate_")) ||
        step.kind === "inspect";
      if (finishesStep) {
        status = "done";
        endedAt = node.endedAt || Date.now();
        durationMs = endedAt - (startedAt || endedAt);
      } else if (status === "pending") {
        status = "running";
      }
    }
    return { ...step, nodeIds, status, startedAt, endedAt, durationMs };
  });
  return { ...plan, steps: newSteps };
}

function ensureTaskByIdOrSession(
  state: { tasksById: Record<string, OrchestratorTaskItem>; activeTaskIdByDoc: Record<string, string> },
  taskId: string,
  sessionId: string,
): OrchestratorTaskItem | null {
  if (taskId && state.tasksById[taskId]) return state.tasksById[taskId];
  if (sessionId) {
    for (const candidate of Object.values(state.tasksById)) {
      if (candidate.sessionId === sessionId) return candidate;
    }
  }
  return null;
}

export const useOrchestratorTaskStore = defineStore("orchestratorTask", {
  state: () => ({
    tasksById: {} as Record<string, OrchestratorTaskItem>,
    taskIdsByDoc: {} as Record<string, string[]>,
    activeTaskIdByDoc: {} as Record<string, string>,
    subscriptions: {} as Record<string, boolean>,
    starting: false,
    lastError: "",
    drawerOpen: false,
    drawerTaskId: "" as string,
    drawerStepId: "" as string,
  }),

  getters: {
    activeTaskForDoc: (state) => {
      return (docId: string) => {
        const taskId = state.activeTaskIdByDoc[docId] || "";
        return taskId ? state.tasksById[taskId] || null : null;
      };
    },
    drawerTask: (state) => {
      return state.drawerTaskId ? state.tasksById[state.drawerTaskId] || null : null;
    },
    /** plan steps for a given task; empty array if no plan declared yet */
    planStepsForTask: (state) => (taskId: string): OrchestratorPlanStep[] => {
      const task = state.tasksById[taskId];
      return task?.plan?.steps ? [...task.plan.steps] : [];
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

    _patchTaskNodes(taskId: string, sessionId: string, mutator: (task: OrchestratorTaskItem) => void) {
      const task = ensureTaskByIdOrSession(this.$state, taskId, sessionId);
      if (!task) return;
      mutator(task);
      task.updatedAt = new Date().toISOString();
      this.tasksById[task.taskId] = { ...task };
    },

    openDrawer(taskId: string, stepId: string = "") {
      if (!taskId) return;
      this.drawerTaskId = taskId;
      this.drawerStepId = stepId;
      this.drawerOpen = true;
    },
    closeDrawer() {
      this.drawerOpen = false;
    },
    selectDrawerStep(stepId: string) {
      this.drawerStepId = stepId;
    },

    _ensureSessionSubscription(sessionId: string) {
      if (!sessionId || this.subscriptions[sessionId]) return;
      const orchestrator = useOrchestratorStore();
      orchestrator.subscribeSession(sessionId, (event, payload) => {
        if (event === "orchestrator.task.step") {
          const taskId = String(payload?.task_id || "");
          if (!taskId) return;
          const previous = this.tasksById[taskId];
          const phase = String(payload?.phase || "planning");
          const summary = String(payload?.summary || "");
          const task: OrchestratorTaskItem = {
            ...emptyTask(taskId, String(payload?.session_id || sessionId), String(payload?.doc_id || previous?.docId || "")),
            ...(previous || {}),
            taskId,
            sessionId: String(payload?.session_id || sessionId),
            docId: String(payload?.doc_id || previous?.docId || ""),
            title: previous?.title || "编排任务",
            status: payload?.status || "pending",
            phase,
            summary,
            currentStepIndex: Number(payload?.step_index || 1),
            stepTotal: Number(payload?.step_total || 4),
            awaitingUser: Boolean(payload?.awaiting_user),
            activeWorker: String(payload?.active_worker || previous?.activeWorker || ""),
            activeSessionMode: String(payload?.active_session_mode || previous?.activeSessionMode || ""),
            activeWorkerProfile: String(payload?.active_worker_profile || previous?.activeWorkerProfile || ""),
            steps: mergeSteps(previous?.steps, payload?.steps as Array<Record<string, unknown>>, phase, summary),
            nodes: previous?.nodes || [],
            pendingDocWrites: previous?.pendingDocWrites || [],
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
            steps: mergeSteps(existing.steps, existing.steps as unknown as Array<Record<string, unknown>>, existing.phase, String(payload?.prompt || "")),
            updatedAt: new Date().toISOString(),
          });
          return;
        }

        if (event === "orchestrator.task.result") {
          const taskId = String(payload?.task_id || "");
          if (!taskId) return;
          const previous = this.tasksById[taskId];
          const resultSummary = String(payload?.content || "");
          this._upsertTask({
            ...emptyTask(taskId, String(payload?.session_id || sessionId), String(payload?.doc_id || previous?.docId || "")),
            ...(previous || {}),
            taskId,
            sessionId: String(payload?.session_id || sessionId),
            docId: String(payload?.doc_id || previous?.docId || ""),
            title: previous?.title || "编排任务",
            status: (payload?.status as TaskStepStatus) || "done",
            phase: "finalize",
            summary: previous?.summary || "",
            currentStepIndex: 4,
            stepTotal: 4,
            resultSummary,
            awaitingUser: false,
            prompt: "",
            artifacts: Array.isArray(payload?.artifacts) ? payload.artifacts : (previous?.artifacts || []),
            workerRuns: Array.isArray(payload?.worker_runs) ? payload.worker_runs : (previous?.workerRuns || []),
            activeWorker: String(payload?.active_worker || previous?.activeWorker || ""),
            activeSessionMode: String(payload?.active_session_mode || previous?.activeSessionMode || ""),
            activeWorkerProfile: String(payload?.active_worker_profile || previous?.activeWorkerProfile || ""),
            steps: previous?.steps?.length
              ? previous.steps.map((step) => ({
                  ...step,
                  status: step.status === "failed" ? step.status : ("done" as TaskStepStatus),
                  detail: step.phase === "finalize" && resultSummary.trim() ? resultSummary : step.detail || "",
                }))
              : defaultSteps().map((step) => ({
                  ...step,
                  status: "done" as TaskStepStatus,
                  detail: step.phase === "finalize" ? resultSummary : "",
                })),
            nodes: previous?.nodes || [],
            pendingDocWrites: previous?.pendingDocWrites || [],
            updatedAt: new Date().toISOString(),
          });
          return;
        }

        // ---------- PLAN DECLARED ----------
        // LLM called declare_plan: render N plan-step tiles immediately.
        if (event === "orchestrator.task.plan_declared") {
          const taskId = String(payload?.task_id || "");
          if (!taskId) return;
          const incomingSteps = Array.isArray(payload?.steps) ? payload.steps : [];
          this._patchTaskNodes(taskId, sessionId, (task) => {
            const plan: OrchestratorPlan = {
              planId: String(payload?.plan_id || ""),
              declaredAt: Number(payload?.declared_at || Date.now()),
              steps: incomingSteps.map((s: Record<string, unknown>, i: number) =>
                normalizePlanStep(s, i),
              ),
            };
            task.plan = plan;
            // re-apply existing nodes onto the new plan (in case plan declared late or revised)
            for (const node of task.nodes) {
              task.plan = applyNodeToPlan(task.plan, node);
            }
          });
          return;
        }

        // ---------- DYNAMIC NODE LIFECYCLE ----------
        // Server emits orchestrator.session.subnode.{started,completed,failed}
        // for every tool call inside tools_node. We turn each into a dynamic
        // node entry on the task so the drawer can show a real timeline.
        if (event.startsWith("orchestrator.session.subnode.")) {
          const status = event.split(".").pop() || "started";
          const title = String(payload?.title || "");
          const detail = String(payload?.detail || payload?.message || "");
          const taskId = this.activeTaskIdByDoc[
            // try resolve via session
            Object.keys(this.activeTaskIdByDoc).find(
              (doc) => this.tasksById[this.activeTaskIdByDoc[doc]]?.sessionId === sessionId,
            ) || ""
          ];
          if (!taskId) return;
          this._patchTaskNodes(taskId, sessionId, (task) => {
            const existing = task.nodes.find((n) => n.toolName === title && (n.status === "running" || n.status === "pending"));
            let touchedNode: OrchestratorNode | null = null;
            if (status === "started") {
              if (existing) {
                touchedNode = existing;
              } else {
                const fresh: OrchestratorNode = {
                  id: `node_${Date.now()}_${task.nodes.length}`,
                  type: "tool",
                  toolName: title,
                  status: "running",
                  startedAt: Date.now(),
                  argsPreview: detail,
                };
                task.nodes.push(fresh);
                touchedNode = fresh;
              }
            } else if (status === "completed" || status === "failed") {
              const node =
                existing ||
                [...task.nodes].reverse().find((n) => n.toolName === title) ||
                null;
              if (node) {
                node.status = status === "failed" ? "failed" : "done";
                node.endedAt = Date.now();
                node.durationMs = node.endedAt - (node.startedAt || node.endedAt);
                node.outputPreview = detail || node.outputPreview;
                touchedNode = node;
              }
            }
            // Reflect this node into the plan (if any)
            if (task.plan && touchedNode) {
              task.plan = applyNodeToPlan(task.plan, touchedNode);
            }
          });
          return;
        }

        // ---------- DOC WRITE STAGED (pending user confirmation) ----------
        if (event === "orchestrator.task.doc_write") {
          const writeId = String(payload?.write_id || "");
          const taskId = String(payload?.task_id || "");
          if (!writeId || !taskId) return;
          const pending: PendingDocWrite = {
            writeId,
            taskId,
            sessionId: String(payload?.session_id || sessionId),
            docId: String(payload?.doc_id || ""),
            kind: String(payload?.kind || "report"),
            title: String(payload?.title || ""),
            content: String(payload?.content || ""),
            placement: String(payload?.placement || "append"),
            citations: Array.isArray(payload?.citations) ? payload.citations : [],
            createdAt: Number(payload?.created_at || Date.now()),
            applied: false,
          };
          this._patchTaskNodes(taskId, sessionId, (task) => {
            // de-dup by writeId
            if (task.pendingDocWrites.find((w) => w.writeId === writeId)) return;
            task.pendingDocWrites = [...task.pendingDocWrites, pending];
            const newNode: OrchestratorNode = {
              id: `docwrite_${writeId}`,
              type: "doc_write",
              toolName: "write_to_doc",
              status: "done",
              startedAt: Date.now(),
              endedAt: Date.now(),
              durationMs: 0,
              writeId,
              writeKind: pending.kind,
              writeTitle: pending.title,
              writeContent: pending.content,
              writePlacement: pending.placement,
              writeApplied: false,
            };
            task.nodes.push(newNode);
            if (task.plan) task.plan = applyNodeToPlan(task.plan, newNode);
          });
          return;
        }

        // ---------- DOC WRITE APPLIED (user pressed insert) ----------
        if (event === "orchestrator.task.doc_write_applied") {
          const writeId = String(payload?.write_id || "");
          const taskId = String(payload?.task_id || "");
          if (!writeId || !taskId) return;
          this._patchTaskNodes(taskId, sessionId, (task) => {
            const pending = task.pendingDocWrites.find((w) => w.writeId === writeId);
            if (pending) pending.applied = true;
            const node = task.nodes.find((n) => n.writeId === writeId);
            if (node) node.writeApplied = true;
          });
          return;
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
            ...emptyTask(taskId, sessionId, opts.docId),
            title: opts.instruction,
            summary: "任务已创建，等待开始。",
          });
          // auto-open the right drawer so users can watch the task run
          this.openDrawer(taskId);
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

    async applyDocWrite(taskId: string, writeId: string) {
      const orchestrator = useOrchestratorStore();
      const task = this.tasksById[taskId];
      if (!task) return;
      await orchestrator.connect();
      await orchestrator.applyDocWrite({
        taskId: task.taskId,
        sessionId: task.sessionId,
        writeId,
      });
    },
  },
});
