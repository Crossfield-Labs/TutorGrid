<!--
  Vertical timeline of dynamic orchestration nodes.
  - Each tool call (delegate_codex / write_to_doc / read_file / ...) is one row.
  - Click a row → emit('select', node) → parent shows NodeDetailSheet inline.
  - Same workerSession.sessionKey rows show a connecting accent strip on the
    left so users can see "this is the same Codex conversation continuing".
-->
<template>
  <div class="node-timeline">
    <div v-if="!nodes.length" class="node-timeline__empty text-medium-emphasis text-caption pa-4 text-center">
      尚未产生编排节点。任务开始后这里会按顺序显示每一次工具调用。
    </div>
    <ol v-else class="node-timeline__list">
      <li
        v-for="(node, idx) in nodes"
        :key="node.id"
        :class="[
          'node-timeline__row',
          `is-${node.status}`,
          { 'is-active': selectedId === node.id }
        ]"
        @click="$emit('select', node)"
      >
        <div class="node-timeline__rail">
          <div class="node-timeline__dot" :class="`is-${node.status}`">
            <v-icon :icon="iconFor(node)" size="14" />
          </div>
          <div v-if="idx < nodes.length - 1" class="node-timeline__line" />
        </div>

        <div class="node-timeline__content">
          <div class="node-timeline__head">
            <span class="node-timeline__name">{{ labelFor(node) }}</span>
            <span class="node-timeline__type">{{ typeLabel(node.type) }}</span>
            <span v-if="node.durationMs !== undefined" class="node-timeline__time">
              {{ formatDuration(node.durationMs) }}
            </span>
          </div>
          <div v-if="node.argsPreview" class="node-timeline__sub">
            {{ truncate(node.argsPreview, 96) }}
          </div>
          <div v-if="node.outputPreview" class="node-timeline__sub node-timeline__sub--out">
            ↳ {{ truncate(node.outputPreview, 110) }}
          </div>
          <div v-if="node.workerSession" class="node-timeline__chips">
            <v-chip size="x-small" variant="tonal" color="primary">
              {{ node.workerSession.worker }}/{{ node.workerSession.mode }}
            </v-chip>
            <v-chip size="x-small" variant="outlined">
              key={{ node.workerSession.sessionKey }}
            </v-chip>
          </div>
          <div v-if="node.type === 'doc_write'" class="node-timeline__chips">
            <v-chip
              size="x-small"
              :color="node.writeApplied ? 'success' : 'warning'"
              variant="tonal"
            >
              {{ node.writeApplied ? "已插入文档" : "待用户确认" }}
            </v-chip>
            <v-chip v-if="node.writeKind" size="x-small" variant="outlined">
              {{ node.writeKind }}
            </v-chip>
          </div>
        </div>
      </li>
    </ol>
  </div>
</template>

<script setup lang="ts">
import type { OrchestratorNode } from "@/stores/orchestratorTaskStore";

defineProps<{
  nodes: OrchestratorNode[];
  selectedId?: string;
}>();

defineEmits<{
  (e: "select", node: OrchestratorNode): void;
}>();

function iconFor(node: OrchestratorNode): string {
  if (node.status === "running") return "mdi-progress-clock";
  if (node.status === "done") return "mdi-check";
  if (node.status === "failed") return "mdi-close";
  if (node.status === "awaiting_user") return "mdi-account-clock-outline";
  if (node.type === "doc_write") return "mdi-file-document-edit-outline";
  return "mdi-circle-small";
}

function labelFor(node: OrchestratorNode): string {
  if (node.toolName) return node.toolName;
  if (node.type === "plan") return "规划";
  if (node.type === "doc_write") return "写入文档";
  if (node.type === "await_user") return "等待用户";
  return "工具";
}

function typeLabel(type: OrchestratorNode["type"]): string {
  if (type === "plan") return "PLAN";
  if (type === "tool") return "TOOL";
  if (type === "doc_write") return "DELIVER";
  if (type === "await_user") return "GATE";
  return "";
}

function truncate(s: string, n: number): string {
  if (!s) return "";
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m${Math.floor((ms % 60_000) / 1000)}s`;
}
</script>

<style scoped lang="scss">
.node-timeline {
  &__list {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  &__row {
    display: flex;
    gap: 12px;
    padding: 6px 4px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.15s;

    &:hover {
      background: rgba(var(--v-theme-on-surface), 0.04);
    }

    &.is-active {
      background: rgba(var(--v-theme-primary), 0.08);
    }
  }

  &__rail {
    width: 22px;
    flex: 0 0 22px;
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  &__dot {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: rgb(var(--v-theme-on-primary));
    background: rgb(var(--v-theme-primary));
    z-index: 1;

    &.is-running {
      background: rgb(var(--v-theme-primary));
      animation: pulse 1.5s ease-in-out infinite;
    }
    &.is-done { background: rgb(var(--v-theme-success)); }
    &.is-failed { background: rgb(var(--v-theme-error)); }
    &.is-awaiting_user { background: rgb(var(--v-theme-warning)); }
    &.is-pending { background: rgba(var(--v-theme-on-surface), 0.2); }
  }

  &__line {
    flex: 1 1 auto;
    width: 2px;
    background: rgba(var(--v-theme-on-surface), 0.12);
    margin-top: 2px;
  }

  &__content {
    flex: 1 1 auto;
    min-width: 0;
    padding-bottom: 8px;
  }

  &__head {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }

  &__name {
    font-size: 13px;
    font-weight: 600;
  }

  &__type {
    font-size: 10px;
    color: rgba(var(--v-theme-on-surface), 0.5);
    letter-spacing: 0.6px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }

  &__time {
    font-size: 11px;
    color: rgba(var(--v-theme-on-surface), 0.55);
    margin-left: auto;
    font-variant-numeric: tabular-nums;
  }

  &__sub {
    margin-top: 2px;
    font-size: 12px;
    color: rgba(var(--v-theme-on-surface), 0.7);
    word-break: break-word;

    &--out {
      color: rgba(var(--v-theme-on-surface), 0.55);
    }
  }

  &__chips {
    margin-top: 4px;
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(var(--v-theme-primary), 0.4); }
  50% { box-shadow: 0 0 0 6px rgba(var(--v-theme-primary), 0); }
}
</style>
