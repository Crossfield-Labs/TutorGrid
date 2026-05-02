<!--
  F09: RAG引用磁贴
  - 渲染RAG检索结果：来源文件 + 页码 + 原文片段 + 相关度分数
  - AI回答中的citation自动生成到右侧
-->
<template>
  <v-card class="citation-tile fill-height" variant="flat" rounded="lg">
    <div class="tile-inner d-flex flex-column">
      <!-- 标题行 -->
      <div class="d-flex align-center gap-2 mb-1">
        <v-icon icon="mdi-bookshelf" color="success" size="18" />
        <span class="text-caption font-weight-medium text-grey-darken-1">
          RAG 引用
        </span>
      </div>

      <!-- 空状态 -->
      <div
        v-if="!items.length"
        class="d-flex flex-column align-center justify-center flex-fill text-grey"
      >
        <v-icon icon="mdi-magnify" size="24" class="mb-1" />
        <span class="text-caption">等待检索结果</span>
      </div>

      <!-- 引用列表 -->
      <div v-else class="citation-list flex-fill">
        <div
          v-for="(item, idx) in items"
          :key="idx"
          class="citation-item mb-1"
        >
          <div class="d-flex align-center gap-1">
            <v-chip size="x-small" variant="tonal" :color="scoreColor(item.score)">
              {{ (item.score * 100).toFixed(0) }}%
            </v-chip>
            <span class="text-caption font-weight-medium text-truncate">
              {{ item.source }}
            </span>
            <span v-if="item.page" class="text-caption text-grey-darken-1 ml-auto">
              第{{ item.page }}页
            </span>
          </div>
          <div class="text-caption text-grey-darken-1 mt-0.5 citation-excerpt">
            {{ truncate(item.chunk) }}
          </div>
        </div>
      </div>
    </div>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from "vue";

export interface CitationItem {
  source: string;
  page?: number;
  chunk: string;
  score: number;
}

const props = withDefaults(
  defineProps<{
    citations?: CitationItem[];
  }>(),
  {
    citations: () => [],
  }
);

const items = computed(() => props.citations || []);

const scoreColor = (score: number) => {
  if (score >= 0.8) return "success";
  if (score >= 0.5) return "warning";
  return "error";
};

const truncate = (text: string, maxLen = 80) => {
  if (!text) return "";
  return text.length > maxLen ? text.slice(0, maxLen) + "…" : text;
};
</script>

<style scoped lang="scss">
@use "./_styles" as t;

.citation-tile {
  @include t.frosted-tile;
  @include t.tile-padding;
  height: 100%;

  .tile-inner {
    height: 100%;
    min-height: 90px;
    overflow: hidden;
  }
}

.citation-list {
  overflow-y: auto;
}

.citation-item {
  padding: 6px 8px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.03);
}

.citation-excerpt {
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
