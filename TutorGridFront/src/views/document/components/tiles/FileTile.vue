<!--
  F09: 文件磁贴
  - 用于展示知识库文件、AI 任务产物或后端返回的 artifact
-->
<template>
  <v-card class="file-tile fill-height" variant="flat" rounded="lg">
    <div class="tile-inner d-flex flex-column align-center justify-center">
      <v-icon :icon="fileIcon" :color="fileColor" size="40" class="mb-2" />
      <div class="file-title text-subtitle-2 font-weight-bold text-center">
        {{ title }}
      </div>
      <div v-if="subtitle" class="file-subtitle text-caption text-medium-emphasis text-center mt-1">
        {{ subtitle }}
      </div>
      <v-btn
        v-if="filePath"
        class="mt-3"
        size="x-small"
        variant="tonal"
        prepend-icon="mdi-open-in-new"
        @click="$emit('open', filePath)"
      >
        打开
      </v-btn>
    </div>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    title: string;
    subtitle?: string;
    filePath?: string;
  }>(),
  {
    subtitle: "",
    filePath: "",
  }
);

defineEmits<{
  (e: "open", filePath: string): void;
}>();

const lowerName = computed(() => `${props.title} ${props.filePath}`.toLowerCase());

const fileIcon = computed(() => {
  if (lowerName.value.endsWith(".pdf")) return "mdi-file-pdf-box";
  if (lowerName.value.endsWith(".csv") || lowerName.value.endsWith(".xlsx")) return "mdi-file-table-box";
  if (lowerName.value.endsWith(".png") || lowerName.value.endsWith(".jpg") || lowerName.value.endsWith(".jpeg")) return "mdi-file-image";
  if (lowerName.value.endsWith(".md") || lowerName.value.endsWith(".txt")) return "mdi-file-document-outline";
  return "mdi-file-outline";
});

const fileColor = computed(() => {
  if (lowerName.value.endsWith(".pdf")) return "red";
  if (lowerName.value.endsWith(".csv") || lowerName.value.endsWith(".xlsx")) return "green";
  if (lowerName.value.endsWith(".png") || lowerName.value.endsWith(".jpg") || lowerName.value.endsWith(".jpeg")) return "indigo";
  return "primary";
});
</script>

<style scoped lang="scss">
@use "./_styles" as t;

.file-tile {
  @include t.frosted-tile;
  @include t.tile-padding;
  height: 100%;
}

:global(.v-theme--dark) .file-tile {
  @include t.frosted-tile-dark;
}

.tile-inner {
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.file-title,
.file-subtitle {
  max-width: 100%;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.file-title {
  -webkit-line-clamp: 2;
}

.file-subtitle {
  -webkit-line-clamp: 2;
}
</style>
