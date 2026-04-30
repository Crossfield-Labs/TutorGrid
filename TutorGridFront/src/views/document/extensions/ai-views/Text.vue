<template>
  <v-card
    variant="flat"
    rounded="lg"
    class="ai-text pa-3"
    :class="{ 'ai-text--selected': selected }"
  >
    <div class="d-flex align-center mb-2">
      <v-icon
        :icon="headerIcon"
        size="18"
        color="primary"
        class="mr-2"
      />
      <span class="text-body-2 font-weight-medium flex-fill">
        {{ headerLabel }}
      </span>
      <v-chip size="x-small" variant="tonal" color="primary" class="mr-1">
        AI
      </v-chip>
      <v-menu>
        <template #activator="{ props: menuProps }">
          <v-btn
            v-bind="menuProps"
            icon="mdi-dots-horizontal"
            size="x-small"
            variant="text"
          />
        </template>
        <v-list density="compact">
          <v-list-item
            prepend-icon="mdi-content-copy"
            title="复制内容"
            @click="copy"
          />
          <v-list-item
            prepend-icon="mdi-trash-can-outline"
            title="删除卡片"
            @click="deleteNode"
          />
        </v-list>
      </v-menu>
    </div>

    <div v-if="html" class="ai-text__body" v-html="html" />
    <pre v-else-if="markdownText" class="ai-text__markdown">{{ markdownText }}</pre>
    <div v-else class="text-caption text-medium-emphasis">（无内容）</div>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { Node as ProsemirrorNode } from "@tiptap/pm/model";
import { useSnackbarStore } from "@/stores/snackbarStore";

const props = defineProps<{
  node: ProsemirrorNode;
  updateAttributes: (attrs: Record<string, any>) => void;
  deleteNode: () => void;
  selected?: boolean;
}>();

const snackbarStore = useSnackbarStore();

const COMMAND_LABEL: Record<string, string> = {
  "explain-selection": "讲解",
  "summarize-selection": "总结",
  "rewrite-selection": "改写",
  "continue-writing": "续写",
  "ask": "AI 回答",
  "rag-query": "知识库回答",
};

const COMMAND_ICON: Record<string, string> = {
  "explain-selection": "mdi-message-text-outline",
  "summarize-selection": "mdi-text-short",
  "rewrite-selection": "mdi-pencil-outline",
  "continue-writing": "mdi-text-long",
  "ask": "mdi-comment-question-outline",
  "rag-query": "mdi-bookshelf",
};

const html = computed<string | null>(() => props.node.attrs?.data?.html || null);
const markdownText = computed<string | null>(
  () => props.node.attrs?.data?.markdown || null
);
const headerLabel = computed(
  () => COMMAND_LABEL[props.node.attrs?.command] || "AI 内容"
);
const headerIcon = computed(
  () => COMMAND_ICON[props.node.attrs?.command] || "mdi-creation"
);

const copy = async () => {
  const tmp = document.createElement("div");
  if (html.value) tmp.innerHTML = html.value;
  else if (markdownText.value) tmp.textContent = markdownText.value;
  const text = tmp.textContent || "";
  try {
    await navigator.clipboard.writeText(text);
    snackbarStore.showSuccessMessage("已复制");
  } catch {
    snackbarStore.showErrorMessage("复制失败");
  }
};
</script>

<style scoped lang="scss">
.ai-text {
  border: 1px solid rgba(var(--v-theme-primary), 0.32);
  background: rgba(var(--v-theme-primary), 0.04);
}

.ai-text--selected {
  border-color: rgb(var(--v-theme-primary));
}

.ai-text__body {
  font-size: 0.95rem;
  line-height: 1.7;
  color: rgba(0, 0, 0, 0.85);

  :deep(h1),
  :deep(h2),
  :deep(h3) {
    font-weight: 600;
    margin: 0.6em 0 0.3em;
  }

  :deep(h1) {
    font-size: 1.25rem;
  }

  :deep(h2) {
    font-size: 1.125rem;
  }

  :deep(h3) {
    font-size: 1rem;
  }

  :deep(p) {
    margin: 0.4em 0;
  }

  :deep(ul),
  :deep(ol) {
    padding-left: 1.4em;
    margin: 0.4em 0;
  }

  :deep(code) {
    background: rgba(0, 0, 0, 0.06);
    padding: 0.1em 0.4em;
    border-radius: 4px;
    font-family: "JetBrainsMono", "Consolas", monospace;
    font-size: 0.9em;
  }

  :deep(strong) {
    font-weight: 600;
  }
}

.ai-text__markdown {
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 0.95rem;
  line-height: 1.7;
  margin: 0;
  color: rgba(0, 0, 0, 0.85);
}
</style>
