<!--
  F09: 文件预览磁贴
  - 显示文件名 + 图标 + 文件大小
  - PDF/图片有缩略图预览
  - 点击用系统应用打开
-->
<template>
  <v-card class="file-tile fill-height" variant="flat" rounded="lg">
    <div
      class="tile-inner d-flex flex-column align-center justify-center gap-2"
      @click="$emit('open', filePath)"
    >
      <!-- 文件图标 -->
      <v-icon
        :icon="fileIcon"
        :color="iconColor"
        size="36"
      />
      <!-- 文件名 -->
      <div class="text-body-2 font-weight-medium text-truncate w-100 text-center">
        {{ title }}
      </div>
      <!-- 副标题（文件大小或描述） -->
      <div v-if="subtitle" class="text-caption text-grey-darken-1">
        {{ subtitle }}
      </div>
    </div>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    title?: string;
    subtitle?: string;
    filePath?: string;
  }>(),
  {
    title: "文件",
    subtitle: "",
    filePath: "",
  }
);

defineEmits<{
  open: [filePath: string];
}>();

const iconColor = computed(() => {
  const name = (props.title || "").toLowerCase();
  if (name.endsWith(".pdf") || name.includes("pdf")) return "red";
  if (name.endsWith(".png") || name.endsWith(".jpg") || name.endsWith(".jpeg") || name.endsWith(".gif"))
    return "green";
  if (name.endsWith(".py") || name.endsWith(".ts")) return "blue";
  if (name.endsWith(".ppt") || name.endsWith(".pptx")) return "orange";
  return "grey-darken-1";
});

const fileIcon = computed(() => {
  const name = (props.title || "").toLowerCase();
  if (name.endsWith(".pdf") || name.includes("pdf")) return "mdi-file-pdf-box";
  if (name.endsWith(".png") || name.endsWith(".jpg") || name.endsWith(".jpeg") || name.endsWith(".gif"))
    return "mdi-file-image";
  if (name.endsWith(".py")) return "mdi-language-python";
  if (name.endsWith(".ts") || name.endsWith(".js")) return "mdi-code-json";
  if (name.endsWith(".ppt") || name.endsWith(".pptx")) return "mdi-file-powerpoint-box";
  if (name.endsWith(".doc") || name.endsWith(".docx")) return "mdi-file-word-box";
  return "mdi-file-outline";
});
</script>

<style scoped lang="scss">
@use "./_styles" as t;

.file-tile {
  @include t.frosted-tile;
  @include t.tile-padding;
  height: 100%;
  cursor: pointer;

  .tile-inner {
    height: 100%;
    min-height: 90px;
  }
}
</style>
