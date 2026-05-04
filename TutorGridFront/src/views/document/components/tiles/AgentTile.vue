<!--
  活跃 Agent 磁贴 - 取代旧 AsidePanel 的 activeAgent 部分
  推荐尺寸 2x2
-->
<template>
  <v-card
    class="agent-tile d-flex flex-column"
    :class="{ 'agent-tile--active': !!agent }"
    elevation="0"
    rounded="lg"
    :ripple="false"
  >
    <div class="d-flex align-center mb-2">
      <v-icon
        :icon="agent ? 'mdi-flash' : 'mdi-flash-outline'"
        :color="agent ? 'warning' : 'grey'"
        size="20"
        class="mr-2"
      />
      <span class="text-subtitle-2 font-weight-bold flex-fill">
        活跃 Agent
      </span>
      <v-btn
        v-if="agent"
        size="x-small"
        icon="mdi-close"
        variant="text"
        @click.stop="$emit('dismiss')"
      />
    </div>

    <template v-if="agent">
      <div class="text-body-2 font-weight-medium mb-1 text-truncate-2">
        {{ agent.title }}
      </div>
      <div class="text-caption text-medium-emphasis mb-2">
        phase: {{ agent.phase }} · worker: {{ agent.worker || "—" }}
      </div>
      <v-spacer />
      <div class="text-caption mb-1 d-flex align-center">
        <span class="flex-fill">进度</span>
        <span class="font-weight-bold">
          {{ Math.round(agent.progress * 100) }}%
        </span>
      </div>
      <v-progress-linear
        :model-value="agent.progress * 100"
        color="warning"
        height="6"
        rounded
      />
    </template>

    <div
      v-else
      class="agent-empty d-flex flex-column align-center justify-center text-center text-caption text-medium-emphasis flex-fill"
    >
      <v-icon icon="mdi-flash-outline" size="28" class="mb-1" />
      <div>暂无运行中的 Agent</div>
      <div class="text-disabled mt-1">编排任务启动后会在这里显示</div>
    </div>
  </v-card>
</template>

<script setup lang="ts">
interface ActiveAgent {
  title: string;
  phase: string;
  worker?: string;
  progress: number;
}

defineProps<{
  agent?: ActiveAgent | null;
}>();

defineEmits<{
  (e: "dismiss"): void;
}>();
</script>

<style scoped lang="scss">
@use "./_styles" as t;

.agent-tile {
  @include t.frosted-tile;
  @include t.tile-padding;
  height: 100%;
  width: 100%;
}

.agent-tile--active {
  @include t.frosted-tile-accent(#ff9800);
}

:global(.v-theme--dark) .agent-tile {
  @include t.frosted-tile-dark;
}

.text-truncate-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.agent-empty {
  min-height: 0;
}
</style>
