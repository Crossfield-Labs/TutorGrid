<template>
  <v-card
    class="document-editor d-flex flex-column card-shadow"
    elevation="0"
  >
    <!-- 工具栏（不参与滚动）-->
    <div v-if="editor" class="editor-toolbar-wrap flex-shrink-0">
      <RichEditorMenubar :editor="editor" />
    </div>

    <EditorBubbleMenu v-if="editor" :editor="editor" @ai-command="onAi" />

    <SlashCommandMenu
      :open="slashState.open"
      :top="slashState.top"
      :left="slashState.left"
      :query="slashState.query"
      :items="SLASH_ITEMS"
      :active-index="slashState.activeIndex"
      @select="onSlashSelect"
      @hover="(i) => (slashState.activeIndex = i)"
    />

    <v-divider />

    <!-- 内容（独立滚动）-->
    <div class="editor-body flex-fill">
      <div class="editor-scroll">
        <editor-content :editor="editor" class="editor-content editor-frame" />
      </div>
    </div>

    <v-divider />

    <!-- 底栏（不参与滚动）-->
    <div
      v-if="editor"
      class="d-flex align-center px-4 py-1 text-caption text-medium-emphasis editor-footer flex-shrink-0"
    >
      <v-icon icon="mdi-text" size="14" class="mr-1" />
      {{ characters }} 字
      <v-divider vertical class="mx-2" />
      <v-icon :icon="wsStatusIcon" :color="wsStatusColor" size="12" class="mr-1" />
      <span>{{ wsStatusText }}</span>
      <v-spacer />
      <v-chip :color="saveStatusColor" size="x-small" variant="tonal">
        <v-icon :icon="saveStatusIcon" size="12" class="mr-1" />
        {{ saveStatusText }}
      </v-chip>
    </div>
  </v-card>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, watch } from "vue";
import { Editor, EditorContent, useEditor } from "@tiptap/vue-3";
import StarterKit from "@tiptap/starter-kit";
import Image from "@tiptap/extension-image";
import Highlight from "@tiptap/extension-highlight";
import RichEditorMenubar from "./RichEditorMenubar.vue";
import EditorBubbleMenu from "./EditorBubbleMenu.vue";
import SlashCommandMenu from "../extensions/SlashCommandMenu.vue";
import type { SlashItem } from "../extensions/SlashCommandMenu.vue";
import {
  SLASH_ITEMS,
  filterSlashItems,
} from "../extensions/slash-command-items";
import { useOrchestratorStore } from "@/stores/orchestratorStore";

interface Props {
  modelValue: string;
  saveStatus?: "idle" | "saving" | "saved" | "error";
  editable?: boolean;
  tileId?: string;
}

const props = withDefaults(defineProps<Props>(), {
  saveStatus: "idle",
  editable: true,
  tileId: "",
});

const orchestratorStore = useOrchestratorStore();

const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
  (e: "ready", editor: Editor): void;
  (e: "aiCommand", command: string, payload?: { selectionText: string }): void;
}>();

const slashState = reactive({
  open: false,
  query: "",
  slashFrom: -1,
  top: 0,
  left: 0,
  activeIndex: 0,
});

const editor = useEditor({
  content: props.modelValue,
  editable: props.editable,
  extensions: [
    StarterKit.configure({
      heading: { levels: [1, 2, 3] },
    }),
    Image.configure({
      inline: false,
      allowBase64: true,
      HTMLAttributes: { class: "doc-image" },
    }),
    Highlight.configure({ multicolor: true }),
    // [TODO F07] AiBubbleNode TipTap 扩展将在这里注册
  ],
  editorProps: {
    handleKeyDown(_view, event) {
      if (!slashState.open) return false;
      const filtered = filterSlashItems(SLASH_ITEMS, slashState.query);
      if (event.key === "ArrowDown") {
        if (filtered.length === 0) return true;
        slashState.activeIndex =
          (slashState.activeIndex + 1) % filtered.length;
        return true;
      }
      if (event.key === "ArrowUp") {
        if (filtered.length === 0) return true;
        slashState.activeIndex =
          (slashState.activeIndex - 1 + filtered.length) % filtered.length;
        return true;
      }
      if (event.key === "Enter") {
        const pick = filtered[slashState.activeIndex];
        if (!pick) return true;
        onSlashSelect(pick);
        return true;
      }
      if (event.key === "Escape") {
        closeSlash();
        return true;
      }
      return false;
    },
  },
  onUpdate({ editor }) {
    emit("update:modelValue", editor.getHTML());
    updateSlashFromEditor();
  },
  onSelectionUpdate() {
    updateSlashFromEditor();
  },
  onCreate({ editor }) {
    emit("ready", editor as Editor);
  },
});

watch(
  () => props.modelValue,
  (val) => {
    if (!editor.value) return;
    if (val === editor.value.getHTML()) return;
    editor.value.commands.setContent(val, { emitUpdate: false } as any);
  }
);

watch(
  () => props.editable,
  (val) => editor.value?.setEditable(val)
);

const characters = computed(() => {
  if (!editor.value) return 0;
  return editor.value.getText().length;
});

const saveStatusText = computed(() => {
  switch (props.saveStatus) {
    case "saving":
      return "保存中…";
    case "saved":
      return "已保存";
    case "error":
      return "保存失败";
    default:
      return "就绪";
  }
});

const saveStatusColor = computed(() => {
  switch (props.saveStatus) {
    case "saving":
      return "warning";
    case "saved":
      return "success";
    case "error":
      return "error";
    default:
      return "grey";
  }
});

const saveStatusIcon = computed(() => {
  switch (props.saveStatus) {
    case "saving":
      return "mdi-cloud-upload-outline";
    case "saved":
      return "mdi-check-circle-outline";
    case "error":
      return "mdi-alert-circle-outline";
    default:
      return "mdi-circle-outline";
  }
});

const wsStatusText = computed(() => {
  switch (orchestratorStore.status) {
    case "connected":
      return "AI 已连接";
    case "connecting":
      return "连接中…";
    case "disconnected":
      return "AI 已断开（mock）";
    case "error":
      return "AI 连接失败（mock）";
    default:
      return "AI 离线（mock）";
  }
});

const wsStatusColor = computed(() => {
  switch (orchestratorStore.status) {
    case "connected":
      return "success";
    case "connecting":
      return "warning";
    case "error":
      return "error";
    default:
      return "grey";
  }
});

const wsStatusIcon = computed(() => {
  switch (orchestratorStore.status) {
    case "connected":
      return "mdi-circle";
    case "connecting":
      return "mdi-loading";
    case "error":
      return "mdi-alert";
    default:
      return "mdi-circle-outline";
  }
});

// [TODO F07] 旧 ai-block 流水线已清理。F07 阶段在这里挂入：
//   - SSE 客户端调用 /api/chat/stream
//   - AiBubbleNode 节点的流式 delta 追加
//   - 统一消息 store 同步（renderIn: 'both'）
// 旧 runAiCommand / runMockPipeline / runLivePipeline / runRagPipeline /
// streamTextLikeBlock / streamAgentLifecycle / applyMockRag / applyTextLikeFinal
// 全部已删除。F07 阶段会引入新的 SSE pipeline。


// ──────────────────────────────────────────────────────────
// AI 命令派发（占位版，F07 阶段重写）
// 现状：所有命令都通过 emit('aiCommand') 上抛给 HyperdocPage，
//      HyperdocPage 暂时显示 snackbar 提示。
// F07 阶段会拆分为：
//   - 文本类（explain/summarize/rewrite/continue/ask）→ 在文档插入 AiBubbleNode + SSE 填充
//   - rag-query → 走 RAG，结果落右侧 CitationTile
//   - do-task → F12 编排链路
// ──────────────────────────────────────────────────────────
const onAi = (command: string) => {
  const ed = editor.value;
  if (!ed) return;
  const { from, to } = ed.state.selection;
  const selectionText = ed.state.doc.textBetween(from, to, "\n");
  emit("aiCommand", command, { selectionText });
};


const closeSlash = () => {
  slashState.open = false;
  slashState.query = "";
  slashState.slashFrom = -1;
  slashState.activeIndex = 0;
};

const updateSlashFromEditor = () => {
  const ed = editor.value;
  if (!ed) {
    closeSlash();
    return;
  }
  const { selection } = ed.state;
  if (!selection.empty) {
    if (slashState.open) closeSlash();
    return;
  }
  const cursor = selection.from;
  const $pos = ed.state.doc.resolve(cursor);
  if (!$pos.parent.isTextblock) {
    if (slashState.open) closeSlash();
    return;
  }
  const parentStart = $pos.start();
  const textBefore = ed.state.doc.textBetween(parentStart, cursor, "\n");
  const match = /(?:^|\s)(\/)([一-龥\w-]*)$/.exec(textBefore);
  if (!match) {
    if (slashState.open) closeSlash();
    return;
  }
  const slashOffset = match.index + match[0].indexOf("/");
  const slashPos = parentStart + slashOffset;
  const coords = ed.view.coordsAtPos(slashPos);

  slashState.slashFrom = slashPos;
  slashState.query = match[2] || "";
  slashState.top = coords.bottom + 4;
  slashState.left = coords.left;
  if (!slashState.open) {
    slashState.open = true;
    slashState.activeIndex = 0;
  } else {
    const filtered = filterSlashItems(SLASH_ITEMS, slashState.query);
    if (slashState.activeIndex >= filtered.length) {
      slashState.activeIndex = 0;
    }
  }
};

const onSlashSelect = (item: SlashItem) => {
  const ed = editor.value;
  if (!ed) return;
  const slashFrom = slashState.slashFrom;
  const cursorTo = ed.state.selection.from;
  closeSlash();
  if (slashFrom < 0) return;
  ed.chain()
    .focus()
    .deleteRange({ from: slashFrom, to: cursorTo })
    .run();
  emit("aiCommand", item.command, { selectionText: "" });
};

onMounted(() => {
  if (orchestratorStore.status === "idle" || orchestratorStore.status === "disconnected") {
    orchestratorStore.connect().catch((err) => {
      console.warn("[orchestrator] connect failed, will keep retrying / fall back to mock:", err);
    });
  }
});

onBeforeUnmount(() => {
  editor.value?.destroy();
});

defineExpose({ editor });
</script>

<style scoped lang="scss">
@use "./tiles/_styles" as t;

.document-editor {
  @include t.frosted-panel;
  height: 100%;
  min-height: 0;
}

:global(.v-theme--dark) .document-editor {
  @include t.frosted-panel-dark;
}

// 保留 card-shadow 作为兼容类，但不再叠加额外阴影
.card-shadow {
  box-shadow: none !important;
}

.editor-toolbar-wrap {
  background: transparent;
  border-bottom: 1px solid rgba(255, 255, 255, 0.25);
  padding: 8px 10px;
}

// 让 RichEditorMenubar 内部的 perfect-scrollbar 在我们这里看起来融入卡片
:deep(.menuBar) {
  padding: 0 !important;
  border: none !important;
  border-radius: 0 !important;
}

:deep(.menuBar .v-btn) {
  width: 40px;
  height: 40px;
  border-radius: 6px;
  color: rgba(17, 24, 39, 0.82);
}

:deep(.menuBar .v-btn--active) {
  background: rgba(30, 41, 59, 0.1);
  color: rgb(var(--v-theme-primary));
}

.editor-body {
  flex: 1 1 auto;
  min-height: 0;
  background: transparent;
  padding: 28px 30px;
  overflow: hidden;
}

.editor-scroll {
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
  padding-right: 8px;
  scrollbar-gutter: stable;
}

.editor-content {
  max-width: 980px;
  margin: 0 auto;
}

// 内层"纸面"——默认透明，只在聚焦时显出浅色描边（参考设计）
.editor-frame {
  min-height: 100%;
  padding: 30px 34px;
  background: transparent;
  border: 2px solid transparent;
  border-radius:  4px 4px 12px 12px;
  transition: border-color 0.15s ease;

  &:focus-within {
    border-color: #c2c7d1;
  }
}

.editor-footer {
  min-height: 34px;
  border-top: 1px solid rgba(255, 255, 255, 0.25);
  background: transparent;
}

.editor-content :deep(.ProseMirror) {
  outline: none;
  font-size: 1rem;
  line-height: 1.75;
  min-height: 100%;

  > * + * {
    margin-top: 0.75em;
  }

  h1 {
    font-size: 1.875rem;
    font-weight: 700;
    margin-top: 1.4em;
  }

  h2 {
    font-size: 1.5rem;
    font-weight: 600;
    margin-top: 1.2em;
  }

  h3 {
    font-size: 1.25rem;
    font-weight: 600;
    margin-top: 1em;
  }

  p {
    margin: 0.5em 0;
  }

  ul,
  ol {
    padding-left: 1.5em;
  }

  li > p {
    margin: 0.2em 0;
  }

  blockquote {
    border-left: 3px solid rgb(var(--v-theme-primary));
    padding: 0.45em 1em;
    color: rgba(0, 0, 0, 0.65);
    background: rgba(var(--v-theme-primary), 0.045);
    border-radius: 0 6px 6px 0;
  }

  code {
    background: rgba(0, 0, 0, 0.06);
    padding: 0.1em 0.4em;
    border-radius: 4px;
    font-family: "JetBrainsMono", "Consolas", monospace;
    font-size: 0.92em;
  }

  pre {
    background: #1e1e2e;
    color: #f5f5f7;
    padding: 0.9em 1.1em;
    border-radius: 8px;
    overflow-x: auto;
    font-family: "JetBrainsMono", "Consolas", monospace;
    font-size: 0.9em;

    code {
      background: transparent;
      color: inherit;
      padding: 0;
    }
  }

  hr {
    border: none;
    border-top: 1px dashed rgba(0, 0, 0, 0.2);
    margin: 1.5em 0;
  }

  mark {
    background: rgba(255, 235, 59, 0.45);
    padding: 0 0.15em;
    border-radius: 3px;
  }

  .doc-image {
    max-width: 100%;
    border-radius: 8px;
    margin: 0.6em 0;
  }
}

.editor-scroll::-webkit-scrollbar {
  width: 10px;
}

.editor-scroll::-webkit-scrollbar-track {
  background: transparent;
}

.editor-scroll::-webkit-scrollbar-thumb {
  background: rgba(100, 116, 139, 0.38);
  border: 2px solid #fafafa;
  border-radius: 999px;
}

.editor-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(71, 85, 105, 0.55);
}

@media (max-width: 959px) {
  .document-editor {
    height: 72vh;
  }

  .editor-body {
    padding: 18px;
  }

  .editor-frame {
    padding: 22px 20px;
  }
}
</style>
