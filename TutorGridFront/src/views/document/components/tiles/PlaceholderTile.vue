<!--
  占位磁贴 - F06 阶段用，仅展示磨砂质感与不同尺寸
  F08/F09 由前端B替换为真实磁贴（FileTile / CitationTile / TaskTile 等）
-->
<template>
  <v-card
    class="placeholder-tile d-flex flex-column"
    elevation="0"
    rounded="lg"
    :ripple="false"
  >
    <div class="d-flex align-center mb-2">
      <v-icon :icon="icon" :color="iconColor" size="20" class="mr-2" />
      <span class="text-subtitle-2 font-weight-bold flex-fill text-truncate">
        {{ title }}
      </span>
      <v-chip size="x-small" variant="tonal" :color="iconColor" class="ml-1">
        {{ size }}
      </v-chip>
    </div>

    <div
      v-if="subtitle"
      class="text-caption text-medium-emphasis mb-2 text-truncate-2"
    >
      {{ subtitle }}
    </div>

    <v-spacer />

    <div class="text-caption text-disabled mt-auto">
      占位磁贴 · {{ size }}
    </div>
  </v-card>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    subtitle?: string;
    icon?: string;
    iconColor?: string;
    size?: "1x1" | "1x2" | "2x2";
  }>(),
  {
    icon: "mdi-shape-outline",
    iconColor: "primary",
    size: "1x1",
    subtitle: "",
  }
);
</script>

<style scoped lang="scss">
@use "./_styles" as t;

.placeholder-tile {
  @include t.frosted-tile;
  @include t.tile-padding;
  height: 100%;
  width: 100%;
}

:global(.v-theme--dark) .placeholder-tile {
  @include t.frosted-tile-dark;
}

.text-truncate-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
