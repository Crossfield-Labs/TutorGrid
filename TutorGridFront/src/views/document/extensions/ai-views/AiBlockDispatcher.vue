<template>
  <node-view-wrapper
    :class="['ai-block-wrapper', selected && 'ai-block-wrapper--selected']"
    :data-kind="node.attrs.kind"
  >
    <Placeholder
      v-if="node.attrs.kind === 'placeholder'"
      :node="node"
    />
    <TextBlock
      v-else-if="node.attrs.kind === 'text'"
      :node="node"
      :update-attributes="updateAttributes"
      :delete-node="deleteNode"
    />
    <Quiz
      v-else-if="node.attrs.kind === 'quiz'"
      :node="node"
      :update-attributes="updateAttributes"
      :delete-node="deleteNode"
    />
    <Flashcard
      v-else-if="node.attrs.kind === 'flashcard'"
      :node="node"
      :update-attributes="updateAttributes"
      :delete-node="deleteNode"
    />
    <Agent
      v-else-if="node.attrs.kind === 'agent'"
      :node="node"
      :update-attributes="updateAttributes"
      :delete-node="deleteNode"
    />
    <Citation
      v-else-if="node.attrs.kind === 'citation'"
      :node="node"
      :update-attributes="updateAttributes"
      :delete-node="deleteNode"
    />
    <UnknownBlock v-else :node="node" :delete-node="deleteNode" />
  </node-view-wrapper>
</template>

<script setup lang="ts">
import { NodeViewWrapper, nodeViewProps } from "@tiptap/vue-3";
import Placeholder from "./Placeholder.vue";
import TextBlock from "./Text.vue";
import Quiz from "./Quiz.vue";
import Flashcard from "./Flashcard.vue";
import Agent from "./Agent.vue";
import Citation from "./Citation.vue";
import UnknownBlock from "./UnknownBlock.vue";

defineProps(nodeViewProps);
</script>

<style scoped lang="scss">
.ai-block-wrapper {
  margin: 14px 0;
}

.ai-block-wrapper--selected {
  outline: 2px solid rgba(var(--v-theme-primary), 0.45);
  outline-offset: 2px;
  border-radius: 12px;
}
</style>
