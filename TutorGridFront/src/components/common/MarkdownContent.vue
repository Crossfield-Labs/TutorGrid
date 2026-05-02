<template>
  <div class="markdown-body" v-html="renderedHtml" />
</template>

<script setup lang="ts">
import { computed } from "vue";
import { renderMarkdown, postProcessLinks } from "@/lib/markdown";

const props = withDefaults(
  defineProps<{
    content?: string;
  }>(),
  {
    content: "",
  }
);

const renderedHtml = computed(() => {
  const text = String(props.content || "");
  if (!text.trim()) return "";
  return postProcessLinks(renderMarkdown(text));
});
</script>

<style scoped lang="scss">
.markdown-body :deep(p) {
  margin: 0 0 0.5em;

  &:last-child {
    margin-bottom: 0;
  }
}

.markdown-body :deep(code) {
  background: rgba(15, 23, 42, 0.08);
  padding: 2px 5px;
  border-radius: 4px;
  font-size: 0.88em;
  font-family: "Source Code Pro", Consolas, monospace;
}

.markdown-body :deep(pre) {
  background: #1e293b;
  color: #e2e8f0;
  padding: 10px 14px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 12.5px;
}

.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
  color: inherit;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0.4em 0;
  padding-left: 1.4em;
}

.markdown-body :deep(blockquote) {
  border-left: 3px solid rgba(15, 23, 42, 0.18);
  padding-left: 10px;
  color: rgba(15, 23, 42, 0.7);
  margin: 0.5em 0;
}

.markdown-body :deep(a) {
  color: rgb(var(--v-theme-primary));
  text-decoration: underline;
}

:global(.v-theme--dark) .markdown-body :deep(code) {
  background: rgba(255, 255, 255, 0.1);
}
</style>
