<!--
  Inline detail sheet for a single orchestration node.
  - Shows args / output / metadata via tabs.
  - For doc_write nodes: shows the staged Markdown deliverable + insert button.
  - Stays inside the right drawer (no full-page navigation).
-->
<template>
  <v-card class="node-detail" elevation="0" rounded="lg" border>
    <v-card-text class="pa-3">
      <div class="d-flex align-center mb-2">
        <span class="text-caption text-medium-emphasis">节点详情</span>
        <v-spacer />
        <v-btn size="x-small" variant="text" icon="mdi-close" @click="$emit('close')" />
      </div>

      <div class="text-body-2 font-weight-medium mb-1">
        {{ node.toolName || node.type }}
      </div>
      <div class="text-caption text-medium-emphasis mb-3">
        {{ statusText }} · {{ formatDuration(node.durationMs) }} · {{ formatTime(node.startedAt) }}
      </div>

      <v-tabs v-model="tab" density="compact" align-tabs="start">
        <v-tab value="output">输出</v-tab>
        <v-tab value="args">参数</v-tab>
        <v-tab v-if="isDocWrite" value="deliverable">交付内容</v-tab>
      </v-tabs>

      <v-divider class="mb-3" />

      <v-window v-model="tab">
        <v-window-item value="output">
          <pre class="node-detail__pre">{{ node.outputPreview || "(暂无输出)" }}</pre>
        </v-window-item>

        <v-window-item value="args">
          <pre class="node-detail__pre">{{ node.argsPreview || "(无参数预览)" }}</pre>
        </v-window-item>

        <v-window-item v-if="isDocWrite" value="deliverable">
          <div class="d-flex align-center ga-2 mb-2">
            <v-chip
              size="small"
              :color="node.writeApplied ? 'success' : 'warning'"
              variant="tonal"
            >
              {{ node.writeApplied ? "已插入文档" : "待用户确认插入" }}
            </v-chip>
            <v-chip v-if="node.writeKind" size="small" variant="outlined">{{ node.writeKind }}</v-chip>
            <v-spacer />
            <v-btn
              v-if="!node.writeApplied"
              size="small"
              color="primary"
              variant="tonal"
              prepend-icon="mdi-import"
              :loading="applying"
              @click="$emit('insert', node)"
            >
              插入到文档
            </v-btn>
          </div>
          <div class="node-detail__deliverable">
            <pre>{{ node.writeContent || "(空)" }}</pre>
          </div>
        </v-window-item>
      </v-window>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { OrchestratorNode } from "@/stores/orchestratorTaskStore";

const props = defineProps<{
  node: OrchestratorNode;
  applying?: boolean;
}>();

defineEmits<{
  (e: "close"): void;
  (e: "insert", node: OrchestratorNode): void;
}>();

const tab = ref<string>("output");

const isDocWrite = computed(() => props.node.type === "doc_write");

watch(
  () => props.node.id,
  () => {
    tab.value = isDocWrite.value ? "deliverable" : "output";
  },
  { immediate: true },
);

const statusText = computed(() => {
  switch (props.node.status) {
    case "running": return "运行中";
    case "done": return "已完成";
    case "failed": return "失败";
    case "awaiting_user": return "等待输入";
    case "interrupted": return "已中断";
    default: return "等待中";
  }
});

function formatDuration(ms: number | undefined): string {
  if (ms === undefined) return "—";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m${Math.floor((ms % 60_000) / 1000)}s`;
}

function formatTime(ms: number): string {
  if (!ms) return "";
  const d = new Date(ms);
  return d.toLocaleTimeString();
}
</script>

<style scoped lang="scss">
.node-detail {
  margin-top: 12px;

  &__pre {
    white-space: pre-wrap;
    word-break: break-word;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
    background: rgba(var(--v-theme-on-surface), 0.04);
    padding: 10px;
    border-radius: 6px;
    max-height: 320px;
    overflow: auto;
  }

  &__deliverable {
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      font-family: inherit;
      font-size: 13px;
      background: rgba(var(--v-theme-primary), 0.04);
      padding: 12px;
      border-radius: 6px;
      max-height: 360px;
      overflow: auto;
    }
  }
}
</style>
