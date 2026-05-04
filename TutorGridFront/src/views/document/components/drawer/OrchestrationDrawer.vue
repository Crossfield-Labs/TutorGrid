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
            <NodeTimeline
              :nodes="task?.nodes || []"
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
const { drawerOpen, drawerTaskId } = storeToRefs(taskStore);

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

watch(drawerTaskId, (id) => {
  selectedNode.value = null;
  applyingWriteId.value = "";
  tab.value = "steps";
  void id;
});

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
}
</style>
