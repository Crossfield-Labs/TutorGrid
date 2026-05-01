<!--
  选中卡片磁贴 - 取代旧 AsidePanel 的 selectedCard 部分
  推荐尺寸 1x1（或 1x2 如内容较长）
-->
<template>
  <v-card
    class="selection-tile d-flex flex-column"
    :class="{ 'selection-tile--active': !!card }"
    elevation="0"
    rounded="lg"
    :ripple="false"
  >
    <div class="d-flex align-center mb-2">
      <v-icon
        :icon="card?.icon || 'mdi-card-search-outline'"
        :color="card ? 'primary' : 'grey'"
        size="20"
        class="mr-2"
      />
      <span class="text-subtitle-2 font-weight-bold flex-fill text-truncate">
        {{ card?.title || "节点详情" }}
      </span>
      <v-btn
        v-if="card"
        size="x-small"
        icon="mdi-close"
        variant="text"
        @click.stop="$emit('clear')"
      />
    </div>

    <template v-if="card">
      <div class="text-caption text-medium-emphasis text-truncate-3">
        {{ card.detail || "暂无详情" }}
      </div>
    </template>

    <div
      v-else
      class="selection-empty d-flex flex-column align-center justify-center text-center text-caption text-medium-emphasis flex-fill"
    >
      <v-icon icon="mdi-cursor-default-click-outline" size="22" class="mb-1" />
      <div>点击文档中的卡片</div>
      <div class="text-disabled">查看详情</div>
    </div>
  </v-card>
</template>

<script setup lang="ts">
interface SelectedCard {
  title?: string;
  icon?: string;
  detail?: string;
}

defineProps<{
  card?: SelectedCard | null;
}>();

defineEmits<{
  (e: "clear"): void;
}>();
</script>

<style scoped lang="scss">
@use "./_styles" as t;

.selection-tile {
  @include t.frosted-tile;
  @include t.tile-padding;
  height: 100%;
  width: 100%;
}

.selection-tile--active {
  @include t.frosted-tile-accent(#1976d2);
}

:global(.v-theme--dark) .selection-tile {
  @include t.frosted-tile-dark;
}

.text-truncate-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.selection-empty {
  min-height: 60px;
}
</style>
