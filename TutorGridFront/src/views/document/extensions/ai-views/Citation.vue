<template>
  <v-card
    variant="flat"
    rounded="lg"
    class="ai-citation pa-3"
    :class="{ 'ai-citation--selected': selected }"
  >
    <div class="d-flex align-center mb-2">
      <v-icon
        icon="mdi-bookshelf"
        size="18"
        color="success"
        class="mr-2"
      />
      <span class="text-body-2 font-weight-medium flex-fill">
        知识库回答
      </span>
      <v-chip
        v-if="courseName"
        size="x-small"
        variant="tonal"
        color="success"
        class="mr-1"
      >
        {{ courseName }}
      </v-chip>
      <v-chip size="x-small" variant="tonal" color="success" class="mr-1">
        引用 {{ chunks.length }}
      </v-chip>
      <v-btn
        icon="mdi-trash-can-outline"
        size="x-small"
        variant="text"
        @click="deleteNode"
      />
    </div>

    <div v-if="question" class="ai-citation__question text-caption text-medium-emphasis mb-2">
      <v-icon icon="mdi-help-circle-outline" size="12" class="mr-1" />
      {{ question }}
    </div>

    <div v-if="answerHtml" class="ai-citation__answer" v-html="answerHtml" />
    <pre v-else-if="answer" class="ai-citation__answer-pre">{{ answer }}</pre>
    <div v-else class="text-caption text-medium-emphasis">（无回答）</div>

    <v-divider v-if="chunks.length > 0" class="my-2" />

    <v-expansion-panels
      v-if="chunks.length > 0"
      variant="accordion"
      class="ai-citation__chunks"
    >
      <v-expansion-panel>
        <v-expansion-panel-title class="text-caption">
          <v-icon icon="mdi-format-list-numbered" size="14" class="mr-1" />
          展开 {{ chunks.length }} 条引用
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-list density="compact" class="ai-citation__chunk-list">
            <v-list-item
              v-for="(chunk, i) in chunks"
              :key="chunk.chunkId || i"
              rounded="md"
              class="ai-citation__chunk-item"
            >
              <template #prepend>
                <v-avatar size="22" color="success" variant="tonal" class="mr-1">
                  <span class="text-caption">{{ i + 1 }}</span>
                </v-avatar>
              </template>
              <v-list-item-title class="text-caption font-weight-medium">
                <v-icon
                  icon="mdi-file-document-outline"
                  size="13"
                  class="mr-1"
                />
                {{ chunk.fileName || chunk.fileId || "未知来源" }}
                <span
                  v-if="chunk.sourcePage"
                  class="text-medium-emphasis ml-1"
                >
                  · 第 {{ chunk.sourcePage }} 页
                </span>
                <v-chip
                  v-if="chunk.score !== undefined"
                  size="x-small"
                  variant="tonal"
                  class="ml-2"
                >
                  {{ chunk.score.toFixed(2) }}
                </v-chip>
              </v-list-item-title>
              <v-list-item-subtitle class="ai-citation__chunk-content">
                {{ chunk.content }}
              </v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { Node as ProsemirrorNode } from "@tiptap/pm/model";
import type { CitationChunk, CitationData } from "../ai-block-types";

const props = defineProps<{
  node: ProsemirrorNode;
  updateAttributes: (attrs: Record<string, any>) => void;
  deleteNode: () => void;
  selected?: boolean;
}>();

const data = computed<CitationData>(
  () => (props.node.attrs?.data as CitationData) || {}
);

const question = computed(() => data.value.question || "");
const answer = computed(() => data.value.answer || "");
const answerHtml = computed(() => data.value.answerHtml || "");
const courseName = computed(() => data.value.courseName || "");
const chunks = computed<CitationChunk[]>(() => data.value.chunks || []);
</script>

<style scoped lang="scss">
.ai-citation {
  border: 1px solid rgba(var(--v-theme-success), 0.32);
  background: rgba(var(--v-theme-success), 0.03);
}

.ai-citation--selected {
  border-color: rgb(var(--v-theme-success));
}

.ai-citation__question {
  padding: 6px 10px;
  background: rgba(var(--v-theme-success), 0.05);
  border-radius: 6px;
  border-left: 2px solid rgba(var(--v-theme-success), 0.4);
}

.ai-citation__answer {
  font-size: 0.95rem;
  line-height: 1.7;
  color: rgba(0, 0, 0, 0.85);

  :deep(p) {
    margin: 0.4em 0;
  }
  :deep(strong) {
    font-weight: 600;
  }
}

.ai-citation__answer-pre {
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 0.95rem;
  line-height: 1.7;
  margin: 0;
  color: rgba(0, 0, 0, 0.85);
}

.ai-citation__chunks :deep(.v-expansion-panel) {
  background: transparent;
  box-shadow: none;
}

.ai-citation__chunks :deep(.v-expansion-panel-title) {
  min-height: 32px;
  padding: 4px 12px;
}

.ai-citation__chunk-list {
  background: transparent;
  padding: 0;
}

.ai-citation__chunk-item {
  margin-bottom: 4px;
  background: rgba(0, 0, 0, 0.02);
}

.ai-citation__chunk-content {
  white-space: pre-wrap;
  word-break: break-word;
  margin-top: 4px;
  opacity: 0.85;
}
</style>
