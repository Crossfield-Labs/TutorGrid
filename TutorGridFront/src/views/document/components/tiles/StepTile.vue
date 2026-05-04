<!--
  StepTile: per-plan-step tile rendered in TileGrid.
  - LLM declares N steps via declare_plan → N StepTiles appear immediately
    (status=pending) before any execution.
  - As execution progresses, each tile flips pending → running → done
    by matching raw OrchestratorNode events to its plan step.
  - Click → opens OrchestrationDrawer pinned to this step's first node.
-->
<template>
  <v-card
    class="step-tile d-flex flex-column"
    :class="[`is-${step.status}`, `kind-${step.kind}`]"
    elevation="0"
    rounded="lg"
    :ripple="true"
    @click="onOpen"
  >
    <div class="step-tile__head d-flex align-center">
      <v-icon :icon="kindIcon" size="18" :color="iconColor" class="mr-2" />
      <div class="step-tile__index text-caption text-medium-emphasis">
        Step {{ step.index }}
      </div>
      <v-spacer />
      <v-chip size="x-small" :color="statusColor" variant="tonal" density="comfortable">
        {{ statusLabel }}
      </v-chip>
    </div>

    <div class="step-tile__body flex-fill mt-2">
      <div class="step-tile__label text-body-2 font-weight-bold">
        {{ step.label || "未命名步骤" }}
      </div>
      <div v-if="step.brief" class="step-tile__brief text-caption text-medium-emphasis mt-1">
        {{ step.brief }}
      </div>

      <div v-if="step.kind === 'worker' && step.expectedSessionKey" class="step-tile__meta">
        <v-icon icon="mdi-source-branch" size="12" class="mr-1" />
        {{ step.expectedWorker || "worker" }} · key={{ step.expectedSessionKey }}
      </div>
    </div>

    <div class="step-tile__foot d-flex align-center text-caption text-medium-emphasis">
      <span v-if="step.nodeIds.length">
        {{ step.nodeIds.length }} 节点
      </span>
      <v-spacer />
      <span v-if="durationLabel">{{ durationLabel }}</span>
      <v-icon icon="mdi-chevron-right" size="14" class="ml-1" />
    </div>

    <!-- thin progress strip at bottom -->
    <div class="step-tile__rail">
      <div :class="['step-tile__rail-fill', `is-${step.status}`]" />
    </div>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from "vue";
import {
  useOrchestratorTaskStore,
  type OrchestratorPlanStep,
  type TaskStepStatus,
} from "@/stores/orchestratorTaskStore";

const props = defineProps<{
  step: OrchestratorPlanStep;
  taskId: string;
}>();

const taskStore = useOrchestratorTaskStore();

const kindIcon = computed(() => {
  switch (props.step.kind) {
    case "worker": return "mdi-account-hard-hat-outline";
    case "doc_write": return "mdi-file-document-edit-outline";
    case "await_user": return "mdi-account-clock-outline";
    case "inspect": return "mdi-magnify";
    default: return "mdi-circle-medium";
  }
});

const iconColor = computed(() => {
  if (props.step.status === "running") return "primary";
  if (props.step.status === "done") return "success";
  if (props.step.status === "failed") return "error";
  if (props.step.status === "awaiting_user") return "warning";
  return "grey";
});

const statusColor = computed(() => statusColorOf(props.step.status));
const statusLabel = computed(() => statusLabelOf(props.step.status));

const durationLabel = computed(() => {
  const ms = props.step.durationMs;
  if (!ms) {
    if (props.step.status === "running" && props.step.startedAt) {
      const live = Date.now() - props.step.startedAt;
      return live > 1000 ? `${Math.floor(live / 1000)}s` : "";
    }
    return "";
  }
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m${Math.floor((ms % 60_000) / 1000)}s`;
});

function statusColorOf(s: TaskStepStatus): string {
  if (s === "running") return "primary";
  if (s === "done") return "success";
  if (s === "failed") return "error";
  if (s === "awaiting_user") return "warning";
  if (s === "interrupted") return "warning";
  return "grey";
}

function statusLabelOf(s: TaskStepStatus): string {
  if (s === "running") return "执行中";
  if (s === "done") return "完成";
  if (s === "failed") return "失败";
  if (s === "awaiting_user") return "等待";
  if (s === "interrupted") return "中断";
  return "待办";
}

function onOpen() {
  // Open drawer pinned to this task AND filtered to this step's raw nodes.
  taskStore.openDrawer(props.taskId, props.step.id);
}
</script>

<style scoped lang="scss">
@use "./_styles" as t;

.step-tile {
  @include t.frosted-tile;
  @include t.tile-padding;
  height: 100%;
  width: 100%;
  position: relative;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
  }

  &.is-running {
    box-shadow: 0 0 0 2px rgba(var(--v-theme-primary), 0.3);
  }
  &.is-done {
    box-shadow: 0 0 0 1px rgba(var(--v-theme-success), 0.25);
  }
  &.is-failed {
    box-shadow: 0 0 0 1px rgba(var(--v-theme-error), 0.4);
  }

  &__head {
    flex: 0 0 auto;
  }

  &__index {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    letter-spacing: 0.4px;
  }

  &__body {
    min-height: 0;
  }

  &__label {
    line-height: 1.25;
    word-break: break-word;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  &__brief {
    line-height: 1.3;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  &__meta {
    margin-top: 6px;
    font-size: 11px;
    color: rgba(var(--v-theme-on-surface), 0.55);
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__foot {
    flex: 0 0 auto;
    margin-top: 8px;
  }

  &__rail {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: rgba(var(--v-theme-on-surface), 0.06);
  }

  &__rail-fill {
    height: 100%;
    width: 0%;
    background: rgba(var(--v-theme-on-surface), 0.18);
    transition: width 0.4s ease, background 0.3s;
    &.is-pending { width: 0%; }
    &.is-running {
      width: 60%;
      background: linear-gradient(
        90deg,
        rgba(var(--v-theme-primary), 0.4),
        rgb(var(--v-theme-primary)),
        rgba(var(--v-theme-primary), 0.4)
      );
      animation: step-rail-slide 1.6s linear infinite;
    }
    &.is-done {
      width: 100%;
      background: rgb(var(--v-theme-success));
    }
    &.is-failed {
      width: 100%;
      background: rgb(var(--v-theme-error));
    }
    &.is-awaiting_user {
      width: 80%;
      background: rgb(var(--v-theme-warning));
    }
  }
}

:global(.v-theme--dark) .step-tile {
  @include t.frosted-tile-dark;
}

@keyframes step-rail-slide {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}
</style>
