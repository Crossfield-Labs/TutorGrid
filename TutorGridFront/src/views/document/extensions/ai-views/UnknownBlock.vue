<template>
  <v-card variant="flat" rounded="lg" class="ai-unknown pa-3">
    <div class="d-flex align-center">
      <v-icon
        icon="mdi-help-circle-outline"
        size="18"
        color="grey-darken-1"
        class="mr-2"
      />
      <div class="flex-fill">
        <div class="text-body-2 font-weight-medium">未知 AI 卡片</div>
        <div class="text-caption text-medium-emphasis">
          kind = {{ node.attrs.kind }}
        </div>
      </div>
      <v-btn
        icon="mdi-close"
        size="x-small"
        variant="text"
        @click="deleteNode"
      />
    </div>
  </v-card>
</template>

<script setup lang="ts">
import type { Node as ProsemirrorNode } from "@tiptap/pm/model";

defineProps<{
  node: ProsemirrorNode;
  deleteNode: () => void;
}>();
</script>

<style scoped lang="scss">
.ai-unknown {
  border: 1px dashed rgba(0, 0, 0, 0.18);
  background: rgba(0, 0, 0, 0.02);
}
</style>
