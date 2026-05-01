<template>
  <v-card
    variant="flat"
    rounded="lg"
    class="ai-placeholder pa-3"
    :class="{ 'ai-placeholder--selected': selected }"
  >
    <div class="d-flex align-center mb-2">
      <v-icon
        icon="mdi-creation"
        size="18"
        color="primary"
        class="mr-2 ai-placeholder__icon"
      />
      <span class="text-body-2 font-weight-medium text-primary flex-fill">
        {{ label }}
      </span>
      <v-chip size="x-small" variant="tonal" color="primary">AI</v-chip>
    </div>

    <v-progress-linear
      indeterminate
      color="primary"
      height="2"
      rounded
    />

    <div v-if="streamText" class="ai-placeholder__stream mt-3">{{ streamText }}<span class="ai-placeholder__caret">▍</span></div>

    <div v-else class="ai-placeholder__skeleton mt-3">
      <div class="ai-placeholder__bar" style="width: 92%" />
      <div class="ai-placeholder__bar" style="width: 78%" />
      <div class="ai-placeholder__bar" style="width: 64%" />
    </div>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { Node as ProsemirrorNode } from "@tiptap/pm/model";
import { PLACEHOLDER_LABELS } from "../ai-block-types";

const props = defineProps<{
  node: ProsemirrorNode;
  selected?: boolean;
}>();

const label = computed(() => {
  const explicit = props.node.attrs?.data?.label;
  if (explicit) return explicit;
  const cmd = props.node.attrs?.command;
  return PLACEHOLDER_LABELS[cmd] || "AI 思考中";
});

const streamText = computed(() => {
  const s = props.node.attrs?.data?.stream;
  return typeof s === "string" && s.length > 0 ? s : "";
});
</script>

<style scoped lang="scss">
.ai-placeholder {
  border: 1px solid rgba(var(--v-theme-primary), 0.32);
  background: rgba(var(--v-theme-primary), 0.04);
}

.ai-placeholder--selected {
  border-color: rgb(var(--v-theme-primary));
}

.ai-placeholder__icon {
  animation: ai-placeholder-pulse 1.6s ease-in-out infinite;
}

.ai-placeholder__stream {
  font-size: 0.95rem;
  line-height: 1.7;
  color: rgba(0, 0, 0, 0.85);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 320px;
  overflow-y: auto;
}

.ai-placeholder__caret {
  display: inline-block;
  margin-left: 2px;
  color: rgb(var(--v-theme-primary));
  animation: ai-placeholder-caret 0.8s steps(2, start) infinite;
}

@keyframes ai-placeholder-caret {
  to {
    visibility: hidden;
  }
}

.ai-placeholder__skeleton {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ai-placeholder__bar {
  height: 8px;
  border-radius: 4px;
  background: rgba(var(--v-theme-primary), 0.14);
  animation: ai-placeholder-shimmer 1.6s ease-in-out infinite;
}

.ai-placeholder__bar:nth-child(2) {
  animation-delay: 0.15s;
}

.ai-placeholder__bar:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes ai-placeholder-pulse {
  0%, 100% {
    opacity: 0.45;
  }
  50% {
    opacity: 1;
  }
}

@keyframes ai-placeholder-shimmer {
  0%, 100% {
    opacity: 0.4;
  }
  50% {
    opacity: 0.85;
  }
}
</style>
