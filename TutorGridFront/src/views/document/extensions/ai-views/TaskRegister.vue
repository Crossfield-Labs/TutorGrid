<!--
  TaskRegisterNode view: 文档左栏的轻量任务锚
  - 单行卡片，不堆气泡
  - 编排过程的所有可视化在右侧 OrchestrationDrawer
  - 完成后多出"📌 插入报告到文档"按钮（用户主动决定）
-->
<template>
  <NodeViewWrapper class="task-register" data-drag-handle>
    <div class="task-register__row">
      <v-icon size="18" :color="iconColor" :icon="iconName" class="task-register__icon" />
      <div class="task-register__body">
        <div class="task-register__title">
          {{ task?.title || node.attrs.selectionPreview || "编排任务" }}
        </div>
        <div class="task-register__meta">
          <span :class="['task-register__status', `is-${statusKey}`]">{{ statusLabel }}</span>
          <span v-if="task?.activeWorker" class="task-register__sep">·</span>
          <span v-if="task?.activeWorker" class="task-register__worker">
            {{ task.activeWorker }}{{ task.activeSessionMode ? `/${task.activeSessionMode}` : "" }}
          </span>
          <span v-if="nodeCount" class="task-register__sep">·</span>
          <span v-if="nodeCount" class="task-register__steps">{{ nodeCount }} 步</span>
        </div>
      </div>

      <div class="task-register__actions">
        <v-btn
          v-for="pending in pendingDocWrites"
          :key="pending.writeId"
          size="small"
          color="primary"
          variant="tonal"
          prepend-icon="mdi-import"
          :loading="applyingWriteId === pending.writeId"
          @click="onApplyDocWrite(pending.writeId)"
        >
          插入报告到文档
        </v-btn>
        <v-btn
          size="small"
          variant="text"
          prepend-icon="mdi-page-layout-sidebar-right"
          @click="onOpenDrawer"
        >
          打开编排
        </v-btn>
      </div>
    </div>

    <!-- applied 之后，节点降级为引用锚（仍轻量，留作书签） -->
    <div v-if="hasAppliedReport" class="task-register__applied">
      <v-icon size="14" icon="mdi-check-circle" color="success" class="mr-1" />
      报告已插入到文档下方 · 此锚记录任务来源
    </div>
  </NodeViewWrapper>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { NodeViewWrapper, type NodeViewProps } from "@tiptap/vue-3";
import { useOrchestratorTaskStore, type TaskStepStatus } from "@/stores/orchestratorTaskStore";

const props = defineProps<NodeViewProps>();

const taskStore = useOrchestratorTaskStore();
const applyingWriteId = ref("");

const task = computed(() => {
  const id = String(props.node.attrs.taskId || "");
  return id ? taskStore.tasksById[id] || null : null;
});

const pendingDocWrites = computed(() =>
  (task.value?.pendingDocWrites || []).filter((w) => !w.applied),
);

const hasAppliedReport = computed(() =>
  (task.value?.pendingDocWrites || []).some((w) => w.applied),
);

const nodeCount = computed(() => task.value?.nodes.length || 0);

const statusKey = computed<TaskStepStatus>(() => {
  if (!task.value) return "pending";
  return task.value.status || "pending";
});

const statusLabel = computed(() => {
  const status = statusKey.value;
  if (status === "running") return "编排中";
  if (status === "awaiting_user") return "等待补充输入";
  if (status === "done") return "已完成";
  if (status === "failed") return "执行失败";
  if (status === "interrupted") return "已中断";
  return "已创建";
});

const iconName = computed(() => {
  const status = statusKey.value;
  if (status === "running") return "mdi-progress-clock";
  if (status === "done") return "mdi-check-circle-outline";
  if (status === "failed") return "mdi-alert-circle-outline";
  if (status === "awaiting_user") return "mdi-account-clock-outline";
  if (status === "interrupted") return "mdi-pause-circle-outline";
  return "mdi-clipboard-text-outline";
});

const iconColor = computed(() => {
  const status = statusKey.value;
  if (status === "running") return "primary";
  if (status === "done") return "success";
  if (status === "failed") return "error";
  if (status === "awaiting_user") return "warning";
  return "grey";
});

function onOpenDrawer() {
  const id = String(props.node.attrs.taskId || "");
  if (id) taskStore.openDrawer(id);
}

async function onApplyDocWrite(writeId: string) {
  const id = String(props.node.attrs.taskId || "");
  if (!id || applyingWriteId.value) return;
  applyingWriteId.value = writeId;
  try {
    await taskStore.applyDocWrite(id, writeId);
    const pending = taskStore.tasksById[id]?.pendingDocWrites.find((w) => w.writeId === writeId);
    if (!pending) return;
    // Insert the markdown as a sibling AiBubble (or as inline content) right
    // after this anchor. We rely on the editor instance from props.
    const editor = props.editor;
    const pos = props.getPos?.();
    if (typeof pos !== "number" || !editor) return;
    const insertAt = pos + props.node.nodeSize;
    editor
      .chain()
      .focus(insertAt)
      .insertContentAt(insertAt, [
        { type: "heading", attrs: { level: 3 }, content: [{ type: "text", text: pending.title || "AI 实验报告" }] },
        ...markdownToTiptapBlocks(pending.content),
        { type: "paragraph" },
      ])
      .run();
  } finally {
    applyingWriteId.value = "";
  }
}

/**
 * Minimal markdown -> tiptap block converter:
 * - splits by blank lines
 * - paragraphs and headings supported, fallback to paragraph
 *
 * (We keep this conservative on purpose; if richer markdown is needed later,
 * swap in a proper md->prosemirror parser. The task-register node is the
 * anchor; the inserted blocks are normal editable document content.)
 */
function markdownToTiptapBlocks(md: string): Array<Record<string, unknown>> {
  const lines = (md || "").split(/\r?\n/);
  const blocks: Array<Record<string, unknown>> = [];
  let buffer: string[] = [];
  const flushParagraph = () => {
    const text = buffer.join("\n").trim();
    buffer = [];
    if (!text) return;
    blocks.push({ type: "paragraph", content: [{ type: "text", text }] });
  };
  for (const raw of lines) {
    const line = raw.replace(/\s+$/, "");
    if (!line.trim()) {
      flushParagraph();
      continue;
    }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      flushParagraph();
      blocks.push({
        type: "heading",
        attrs: { level: Math.min(6, Math.max(1, heading[1].length)) },
        content: [{ type: "text", text: heading[2] }],
      });
      continue;
    }
    buffer.push(line);
  }
  flushParagraph();
  return blocks;
}
</script>

<style scoped lang="scss">
.task-register {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 12px;
  padding: 10px 14px;
  margin: 12px 0;
  background: rgba(var(--v-theme-surface), 0.6);
  backdrop-filter: blur(8px);
  display: flex;
  flex-direction: column;
  gap: 6px;

  &__row {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  &__icon {
    flex: 0 0 auto;
  }

  &__body {
    flex: 1 1 auto;
    min-width: 0;
  }

  &__title {
    font-size: 14px;
    font-weight: 600;
    line-height: 1.3;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__meta {
    margin-top: 2px;
    font-size: 12px;
    color: rgba(var(--v-theme-on-surface), 0.6);
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px;
  }

  &__status {
    font-weight: 500;
    &.is-running { color: rgb(var(--v-theme-primary)); }
    &.is-done { color: rgb(var(--v-theme-success)); }
    &.is-failed { color: rgb(var(--v-theme-error)); }
    &.is-awaiting_user { color: rgb(var(--v-theme-warning)); }
    &.is-interrupted { color: rgb(var(--v-theme-warning)); }
  }

  &__sep {
    opacity: 0.5;
  }

  &__actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 0 0 auto;
  }

  &__applied {
    font-size: 12px;
    color: rgba(var(--v-theme-on-surface), 0.6);
    padding-left: 30px;
  }
}
</style>
