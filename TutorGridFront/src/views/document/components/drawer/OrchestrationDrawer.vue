<!--
  Right-side drawer that hosts the dynamic orchestration view for the active task.
  - Steps tab:    NodeTimeline + (optional) NodeDetailSheet
  - Artifacts:    ArtifactList
  - Logs:         worker_runs raw stdout

  This is the SOLE place where orchestration progress is visualised in the
  hyperdoc workspace. The document body itself never accumulates AI bubbles.
-->
<template>
  <v-navigation-drawer
    v-model="open"
    location="right"
    width="420"
    :scrim="false"
    temporary
    elevation="6"
    class="orchestration-drawer"
  >
    <div class="orchestration-drawer__shell d-flex flex-column">
      <!-- Header -->
      <header class="orchestration-drawer__header pa-4">
        <div class="d-flex align-center">
          <v-icon icon="mdi-cog-sync-outline" color="primary" class="mr-2" />
          <span class="text-subtitle-2 font-weight-bold flex-fill text-truncate">
            {{ task?.title || "编排任务" }}
          </span>
          <!-- 任务切换器：多任务时点头部能切 -->
          <v-menu v-if="taskList.length > 1">
            <template #activator="{ props: menuProps }">
              <v-btn v-bind="menuProps" size="small" variant="text" icon="mdi-swap-horizontal" />
            </template>
            <v-list density="compact">
              <v-list-item
                v-for="t in taskList"
                :key="t.taskId"
                :active="t.taskId === task?.taskId"
                @click="taskStore.openDrawer(t.taskId)"
              >
                <v-list-item-title class="text-body-2">{{ t.title || t.taskId }}</v-list-item-title>
                <v-list-item-subtitle class="text-caption">
                  {{ taskStatusText(t.status) }} · {{ t.nodes.length }} 节点
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-menu>
          <v-btn size="small" icon="mdi-close" variant="text" @click="onClose" />
        </div>
        <div v-if="task" class="text-caption text-medium-emphasis mt-1 d-flex flex-wrap ga-2 align-center">
          <span :class="['orchestration-drawer__status', `is-${task.status}`]">
            {{ statusLabel }}
          </span>
          <span v-if="task.activeWorker">
            · {{ task.activeWorker }}<span v-if="task.activeSessionMode">/{{ task.activeSessionMode }}</span>
          </span>
          <span>· {{ task.nodes.length }} 节点</span>
          <span v-if="pendingCount">· {{ pendingCount }} 个待插入交付</span>
        </div>
        <div v-else class="text-caption text-medium-emphasis mt-1">
          当前没有进行中的编排任务。在文档中选中文字 → BubbleMenu → 「执行任务」 启动一个。
        </div>
      </header>

      <v-divider />

      <!-- Tabs -->
      <v-tabs v-model="tab" density="comfortable" align-tabs="start" grow>
        <v-tab value="steps">
          <v-icon icon="mdi-timeline-text-outline" size="16" class="mr-1" />
          步骤
        </v-tab>
        <v-tab value="artifacts">
          <v-icon icon="mdi-folder-outline" size="16" class="mr-1" />
          产物 ({{ task?.artifacts.length || 0 }})
        </v-tab>
        <v-tab value="logs">
          <v-icon icon="mdi-text-box-outline" size="16" class="mr-1" />
          日志
        </v-tab>
      </v-tabs>

      <v-divider />

      <!-- Body -->
      <div class="orchestration-drawer__body flex-fill">
        <v-window v-model="tab" class="h-100">
          <!-- Steps -->
          <v-window-item value="steps" class="pa-4">
            <!-- 顶部：plan 概览（LLM declare_plan 后立刻显示）-->
            <div v-if="task?.plan?.steps?.length" class="orchestration-drawer__plan mb-4">
              <div class="text-caption text-medium-emphasis mb-1">
                计划链路（{{ task.plan.steps.length }} 步）
              </div>
              <div
                v-for="step in task.plan.steps"
                :key="step.id"
                :class="['orchestration-drawer__plan-row', `is-${step.status}`, { 'is-active': activeStepId === step.id }]"
                @click="onSelectStep(step.id)"
              >
                <div :class="['orchestration-drawer__plan-dot', `is-${step.status}`]">
                  {{ step.index }}
                </div>
                <div class="flex-fill min-w-0">
                  <div class="text-body-2 font-weight-medium text-truncate">{{ step.label }}</div>
                  <div class="text-caption text-medium-emphasis text-truncate">
                    {{ planStatusLabel(step.status) }}<span v-if="step.brief"> · {{ step.brief }}</span>
                  </div>
                </div>
                <span class="text-caption text-medium-emphasis">{{ step.nodeIds.length }} 节点</span>
              </div>
            </div>

            <NodeTimeline
              :nodes="filteredNodes"
              :selected-id="selectedNode?.id"
              @select="onSelectNode"
            />
            <NodeDetailSheet
              v-if="selectedNode"
              :node="selectedNode"
              :applying="applyingWriteId === selectedNode.writeId"
              @close="selectedNode = null"
              @insert="onInsertDocWrite"
            />
          </v-window-item>

          <!-- Artifacts -->
          <v-window-item value="artifacts" class="pa-2">
            <ArtifactList
              :artifacts="task?.artifacts || []"
              :workspace="workspace"
            />
          </v-window-item>

          <!-- Logs -->
          <v-window-item value="logs" class="pa-4">
            <div v-if="!task?.workerRuns?.length" class="text-caption text-medium-emphasis text-center pa-4">
              没有 worker 运行日志。
            </div>
            <div v-else>
              <details
                v-for="(run, idx) in task.workerRuns"
                :key="idx"
                class="orchestration-drawer__log"
                :open="idx === 0"
              >
                <summary>
                  <strong>{{ String(run.worker || "worker") }}</strong>
                  <span class="text-caption text-medium-emphasis ml-2">
                    {{ run.success ? "ok" : "failed" }}
                  </span>
                  <span v-if="run.session" class="text-caption text-medium-emphasis ml-2">
                    {{ ((run.session as Record<string, unknown>)?.session_id as string) || "" }}
                  </span>
                </summary>
                <pre class="orchestration-drawer__pre">{{ String(run.output || run.summary || "") }}</pre>
              </details>
            </div>
          </v-window-item>
        </v-window>
      </div>

      <!-- Footer: pending deliverables shortcut -->
      <v-divider v-if="pendingCount" />
      <footer v-if="pendingCount" class="orchestration-drawer__pending pa-3">
        <div class="text-caption text-medium-emphasis mb-2">
          AI 已暂存 {{ pendingCount }} 个交付。点击插入到文档：
        </div>
        <v-btn
          v-for="pending in pendingDocWrites"
          :key="pending.writeId"
          block
          size="small"
          color="primary"
          variant="tonal"
          class="mb-1"
          prepend-icon="mdi-import"
          :loading="applyingWriteId === pending.writeId"
          @click="onInsertPending(pending.writeId)"
        >
          插入「{{ pending.title || pending.kind }}」到文档
        </v-btn>
      </footer>
    </div>
  </v-navigation-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import {
  useOrchestratorTaskStore,
  type OrchestratorNode,
  type OrchestratorTaskItem,
} from "@/stores/orchestratorTaskStore";
import NodeTimeline from "./NodeTimeline.vue";
import NodeDetailSheet from "./NodeDetailSheet.vue";
import ArtifactList from "./ArtifactList.vue";

const taskStore = useOrchestratorTaskStore();
const { drawerOpen, drawerTaskId, drawerStepId } = storeToRefs(taskStore);

const open = computed<boolean>({
  get: () => drawerOpen.value,
  set: (val) => {
    if (val) {
      drawerOpen.value = true;
    } else {
      taskStore.closeDrawer();
    }
  },
});

const task = computed<OrchestratorTaskItem | null>(() => {
  const id = drawerTaskId.value;
  return id ? taskStore.tasksById[id] || null : null;
});

const taskList = computed<OrchestratorTaskItem[]>(() =>
  Object.values(taskStore.tasksById).sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
  ),
);

function taskStatusText(status: string): string {
  if (status === "running") return "编排中";
  if (status === "awaiting_user") return "等待输入";
  if (status === "done") return "已完成";
  if (status === "failed") return "失败";
  if (status === "interrupted") return "已中断";
  return "已创建";
}

const tab = ref<string>("steps");
const selectedNode = ref<OrchestratorNode | null>(null);
const applyingWriteId = ref("");
/** Currently filtered plan-step (null = show all nodes); mirrors store.drawerStepId */
const activeStepId = computed<string>({
  get: () => drawerStepId.value,
  set: (val) => taskStore.selectDrawerStep(val),
});

watch(drawerTaskId, (id) => {
  selectedNode.value = null;
  applyingWriteId.value = "";
  // do NOT reset activeStepId here — store.openDrawer(taskId, stepId) sets
  // both at once, and resetting would clobber the StepTile click intent.
  tab.value = "steps";
  void id;
});

/** Nodes filtered by activeStepId; falls back to all task nodes when no step selected. */
const filteredNodes = computed<OrchestratorNode[]>(() => {
  const all = task.value?.nodes || [];
  if (!activeStepId.value || !task.value?.plan) return all;
  const step = task.value.plan.steps.find((s) => s.id === activeStepId.value);
  if (!step) return all;
  const allowed = new Set(step.nodeIds);
  return all.filter((n) => allowed.has(n.id));
});

function onSelectStep(stepId: string) {
  taskStore.selectDrawerStep(activeStepId.value === stepId ? "" : stepId);
  selectedNode.value = null;
}

function planStatusLabel(status: string): string {
  if (status === "running") return "执行中";
  if (status === "done") return "已完成";
  if (status === "failed") return "失败";
  if (status === "awaiting_user") return "等待用户";
  if (status === "interrupted") return "已中断";
  return "待办";
}

const pendingDocWrites = computed(() =>
  (task.value?.pendingDocWrites || []).filter((w) => !w.applied),
);
const pendingCount = computed(() => pendingDocWrites.value.length);

const workspace = computed(() => {
  const wr = task.value?.workerRuns?.[0] as Record<string, unknown> | undefined;
  const meta = wr?.metadata as Record<string, unknown> | undefined;
  return String(meta?.workspace || "");
});

const statusLabel = computed(() => {
  if (!task.value) return "";
  switch (task.value.status) {
    case "running": return "编排中";
    case "awaiting_user": return "等待补充输入";
    case "done": return "已完成";
    case "failed": return "失败";
    case "interrupted": return "已中断";
    default: return "已创建";
  }
});

function onSelectNode(node: OrchestratorNode) {
  selectedNode.value = node.id === selectedNode.value?.id ? null : node;
}

async function onInsertDocWrite(node: OrchestratorNode) {
  if (!node.writeId || !task.value) return;
  applyingWriteId.value = node.writeId;
  try {
    await taskStore.applyDocWrite(task.value.taskId, node.writeId);
  } finally {
    applyingWriteId.value = "";
  }
}

async function onInsertPending(writeId: string) {
  if (!task.value) return;
  applyingWriteId.value = writeId;
  try {
    await taskStore.applyDocWrite(task.value.taskId, writeId);
  } finally {
    applyingWriteId.value = "";
  }
}

function onClose() {
  taskStore.closeDrawer();
}
</script>

<style scoped lang="scss">
.orchestration-drawer {
  &__shell {
    height: 100%;
  }
  &__body {
    overflow: auto;
  }
  &__header {
    background: linear-gradient(
      135deg,
      rgba(var(--v-theme-primary), 0.06),
      rgba(var(--v-theme-secondary), 0.04)
    );
  }
  &__status {
    font-weight: 500;
    &.is-running { color: rgb(var(--v-theme-primary)); }
    &.is-done { color: rgb(var(--v-theme-success)); }
    &.is-failed { color: rgb(var(--v-theme-error)); }
    &.is-awaiting_user { color: rgb(var(--v-theme-warning)); }
  }
  &__log {
    border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    border-radius: 6px;
    margin-bottom: 8px;
    summary {
      cursor: pointer;
      padding: 8px 12px;
      list-style: none;
    }
  }
  &__pre {
    white-space: pre-wrap;
    word-break: break-word;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    background: rgba(var(--v-theme-on-surface), 0.04);
    padding: 10px 12px;
    margin: 0;
    max-height: 280px;
    overflow: auto;
  }
  &__pending {
    background: rgba(var(--v-theme-primary), 0.04);
  }

  &__plan {
    border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    border-radius: 8px;
    padding: 8px 10px;
    background: rgba(var(--v-theme-surface), 0.4);
  }
  &__plan-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 4px;
    border-radius: 6px;
    cursor: pointer;
    &:hover { background: rgba(var(--v-theme-on-surface), 0.04); }
    &.is-active { background: rgba(var(--v-theme-primary), 0.08); }
  }
  &__plan-dot {
    width: 22px;
    height: 22px;
    flex: 0 0 22px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 600;
    color: rgb(var(--v-theme-on-primary));
    background: rgba(var(--v-theme-on-surface), 0.2);
    &.is-running {
      background: rgb(var(--v-theme-primary));
      animation: drawer-plan-pulse 1.4s ease-in-out infinite;
    }
    &.is-done { background: rgb(var(--v-theme-success)); }
    &.is-failed { background: rgb(var(--v-theme-error)); }
    &.is-awaiting_user { background: rgb(var(--v-theme-warning)); }
  }
}

@keyframes drawer-plan-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(var(--v-theme-primary), 0.4); }
  50% { box-shadow: 0 0 0 6px rgba(var(--v-theme-primary), 0); }
}
</style>
