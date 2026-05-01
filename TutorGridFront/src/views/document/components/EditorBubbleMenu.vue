<template>
  <bubble-menu
    :editor="editor"
    :tippy-options="{ duration: 120, placement: 'top' }"
    :should-show="shouldShow"
  >
    <v-card
      class="bubble-menu-card d-flex align-center pa-1"
      elevation="6"
      rounded="lg"
    >
      <!-- 格式化区 -->
      <v-btn
        icon
        size="small"
        density="comfortable"
        variant="text"
        :active="editor.isActive('bold')"
        @click="editor.chain().focus().toggleBold().run()"
      >
        <v-icon icon="mdi-format-bold" size="18" />
        <v-tooltip activator="parent" location="top" text="加粗" />
      </v-btn>
      <v-btn
        icon
        size="small"
        density="comfortable"
        variant="text"
        :active="editor.isActive('italic')"
        @click="editor.chain().focus().toggleItalic().run()"
      >
        <v-icon icon="mdi-format-italic" size="18" />
        <v-tooltip activator="parent" location="top" text="斜体" />
      </v-btn>
      <v-btn
        icon
        size="small"
        density="comfortable"
        variant="text"
        :active="editor.isActive('strike')"
        @click="editor.chain().focus().toggleStrike().run()"
      >
        <v-icon icon="mdi-format-strikethrough" size="18" />
        <v-tooltip activator="parent" location="top" text="删除线" />
      </v-btn>
      <v-btn
        icon
        size="small"
        density="comfortable"
        variant="text"
        :active="editor.isActive('highlight')"
        @click="editor.chain().focus().toggleHighlight().run()"
      >
        <v-icon icon="mdi-format-color-highlight" size="18" />
        <v-tooltip activator="parent" location="top" text="突出显示" />
      </v-btn>

      <v-divider vertical class="mx-1" />

      <!-- 用户主导命令 -->
      <v-btn
        icon
        size="small"
        density="comfortable"
        variant="text"
        color="primary"
        @click="emit('aiCommand', 'send-to-chat')"
      >
        <v-icon icon="mdi-send-variant-outline" size="18" />
        <v-tooltip activator="parent" location="top" text="发送到 Chat" />
      </v-btn>
      <v-btn
        icon
        size="small"
        density="comfortable"
        variant="text"
        color="primary"
        @click="emit('aiCommand', 'rewrite-selection')"
      >
        <v-icon icon="mdi-pencil-outline" size="18" />
        <v-tooltip activator="parent" location="top" text="改写" />
      </v-btn>
      <v-btn
        icon
        size="small"
        density="comfortable"
        variant="text"
        color="warning"
        @click="emit('aiCommand', 'do-task')"
      >
        <v-icon icon="mdi-flash-outline" size="18" />
        <v-tooltip activator="parent" location="top" text="帮我做这件事" />
      </v-btn>

      <v-divider vertical class="mx-1" />

      <!-- AI 学习命令 -->
      <v-btn
        icon
        size="small"
        density="comfortable"
        variant="text"
        color="primary"
        @click="emit('aiCommand', 'explain-selection')"
      >
        <v-icon icon="mdi-message-text-outline" size="18" />
        <v-tooltip activator="parent" location="top" text="讲解" />
      </v-btn>
      <v-btn
        icon
        size="small"
        density="comfortable"
        variant="text"
        color="primary"
        @click="emit('aiCommand', 'summarize-selection')"
      >
        <v-icon icon="mdi-text-short" size="18" />
        <v-tooltip activator="parent" location="top" text="总结" />
      </v-btn>
      <v-btn
        icon
        size="small"
        density="comfortable"
        variant="text"
        color="primary"
        @click="emit('aiCommand', 'continue-writing')"
      >
        <v-icon icon="mdi-text-long" size="18" />
        <v-tooltip activator="parent" location="top" text="续写" />
      </v-btn>

      <v-divider vertical class="mx-1" />

      <!-- 知识库 -->
      <v-btn
        icon
        size="small"
        density="comfortable"
        variant="text"
        color="success"
        @click="emit('aiCommand', 'rag-query')"
      >
        <v-icon icon="mdi-bookshelf" size="18" />
        <v-tooltip activator="parent" location="top" text="问知识库" />
      </v-btn>
    </v-card>
  </bubble-menu>
</template>

<script setup lang="ts">
import type { Editor } from "@tiptap/vue-3";
import { BubbleMenu } from "@tiptap/vue-3";

defineProps<{ editor: Editor }>();

const emit = defineEmits<{
  (e: "aiCommand", command: string): void;
}>();

const shouldShow = ({ editor, from, to }: any) => {
  // 仅在选中非空文本时显示
  return from !== to && !editor.state.selection.empty;
};
</script>

<style scoped lang="scss">
.bubble-menu-card {
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgba(0, 0, 0, 0.08);
}
</style>
