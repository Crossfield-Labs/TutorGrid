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
import { AiBubbleNode } from "../extensions/ai-bubble-node";
import { useMessageStore } from "@/stores/messageStore";
import { useChatSessionStore } from "@/stores/chatSessionStore";
import { useSnackbarStore } from "@/stores/snackbarStore";
import { streamChat } from "@/lib/chat-sse";
import { useDocumentEditorBus } from "@/composables/useDocumentEditorBus";

interface Props {
  modelValue: string;
  saveStatus?: "idle" | "saving" | "saved" | "error";
  editable?: boolean;
  tileId?: string;
  sessionId: string;
}

const props = withDefaults(defineProps<Props>(), {
  saveStatus: "idle",
  editable: true,
  tileId: "",
  sessionId: "",
});

const messageStore = useMessageStore();
const chatSession = useChatSessionStore();
const snackbarStore = useSnackbarStore();
// Step 2 跨视图：注册自己到 EditorBus，让浮窗 Chat 能"插入到文档"
const editorBus = useDocumentEditorBus();

const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
  (e: "ready", editor: Editor): void;
  (e: "aiCommand", command: string, payload?: { selectionText: string }): void;
  (e: "taskCommand", instruction: string): void;
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
    AiBubbleNode,
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

// AI 状态：Chat SSE 是按请求发起，没有持久连接，所以默认"就绪"
// 编排 WS 状态留给 F12 task 时用，不在这里展示
const wsStatusText = computed(() => "AI 就绪");
const wsStatusColor = computed(() => "success");
const wsStatusIcon = computed(() => "mdi-circle");

// ──────────────────────────────────────────────────────────
// F07 · AI 命令派发：在文档插入 AiBubbleNode + 走 Chat SSE
// ──────────────────────────────────────────────────────────

const COMMAND_LABELS: Record<string, string> = {
  "explain-selection": "讲解",
  "summarize-selection": "总结",
  "rewrite-selection": "改写",
  "continue-writing": "续写",
  "rag-query": "问知识库",
  "do-task": "执行任务",
  ask: "提问",
};

/** 按命令构造 (展示给用户的文本, 实际发给 LLM 的 prompt) */
function buildCommandPrompt(
  command: string,
  selectionText: string,
  recentParagraphs: string[]
): { displayText: string; prompt: string } {
  const sel = selectionText.trim();
  const ctx = recentParagraphs.join("\n").trim();
  const fallback = sel || ctx || "（空）";
  switch (command) {
    case "explain-selection":
      return {
        displayText: sel ? `讲解：${truncate(sel, 60)}` : "[讲解上文]",
        prompt: `请讲解以下内容，用通俗易懂的方式说明核心概念：\n\n${fallback}`,
      };
    case "summarize-selection":
      return {
        displayText: sel ? `总结：${truncate(sel, 60)}` : "[总结上文]",
        prompt: `请用一句话主旨 + 三个要点的格式总结以下内容：\n\n${fallback}`,
      };
    case "rewrite-selection":
      return {
        displayText: sel ? `改写：${truncate(sel, 60)}` : "[改写上文]",
        prompt: `请重写以下文字，使其更清晰、简洁、通顺：\n\n${fallback}`,
      };
    case "continue-writing":
      return {
        displayText: "[续写上文]",
        prompt: `请承接以下内容继续写一段，保持风格一致：\n\n${ctx || sel || ""}`,
      };
    case "rag-query":
      return {
        displayText: sel || ctx ? truncate(sel || ctx, 80) : "[问知识库]",
        prompt: sel || ctx || "请基于课程知识库总结一下重点",
      };
    case "do-task":
      return {
        displayText: sel ? `执行：${truncate(sel, 60)}` : "[执行任务]",
        prompt: `请帮我完成：${sel || ctx || "（请补充任务描述）"}`,
      };
    case "ask":
      return {
        displayText: ctx ? `[基于上文提问]` : "[提问 AI]",
        prompt: ctx
          ? `基于以下我刚写的内容，给我一些建议或补充说明：\n\n${ctx}`
          : "请简单介绍一下我们正在讨论的主题。",
      };
    default:
      return { displayText: sel || `[${command}]`, prompt: sel || command };
  }
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return text.slice(0, max) + "…";
}

/** 取光标附近最多 3 段作为上下文 */
function getRecentParagraphs(): string[] {
  const ed = editor.value;
  if (!ed) return [];
  const text = ed.getText();
  const paragraphs = text
    .split(/\n+/)
    .map((p) => p.trim())
    .filter((p) => !!p);
  return paragraphs.slice(-3);
}

/**
 * 主入口：把一条 AI 命令变成 (用户消息 + AI 占位消息 + AiBubbleNode + SSE 流)
 */
async function runAiCommand(command: string, selectionText: string) {
  const ed = editor.value;
  if (!ed) return;
  if (!props.sessionId) {
    snackbarStore.showErrorMessage("当前文档没有 sessionId，无法发起 AI 对话");
    return;
  }

  const recent = getRecentParagraphs();
  const { displayText, prompt } = buildCommandPrompt(command, selectionText, recent);

  // 1. 写入 store：用户消息 + AI 占位消息
  const userMsg = messageStore.addUserMessage(
    props.sessionId,
    displayText,
    "document",
    command
  );
  const aiMsg = messageStore.startAiMessage(
    props.sessionId,
    "document",
    command
  );

  // 2. 在文档当前位置插入 AiBubbleNode
  ed.chain()
    .focus()
    .insertAiBubble({
      sessionId: props.sessionId,
      userMessageId: userMsg.id,
      aiMessageId: aiMsg.id,
      command,
    })
    .run();

  // 3. 启动 SSE 流
  const tools = ["rag", "tavily"];
  const courseId = chatSession.courseId || "";
  try {
    await streamChat({
      payload: {
        session_id: props.sessionId,
        message: prompt,
        course_id: courseId || undefined,
        tools,
        context: {
          doc_id: props.tileId || undefined,
          recent_paragraphs: recent,
        },
      },
      onEvent: (event) => {
        switch (event.type) {
          case "tool_call":
            messageStore.addToolUsed(props.sessionId, aiMsg.id, event.tool);
            break;
          case "tool_result":
            if (event.citations?.length) {
              messageStore.addCitations(
                props.sessionId,
                aiMsg.id,
                event.citations
              );
            }
            if (event.results?.length) {
              messageStore.addSearchResults(
                props.sessionId,
                aiMsg.id,
                event.results
              );
            }
            break;
          case "delta":
            messageStore.appendDelta(props.sessionId, aiMsg.id, event.content);
            break;
          case "done":
            messageStore.finishMessage(props.sessionId, aiMsg.id);
            break;
          case "error":
            messageStore.failMessage(props.sessionId, aiMsg.id, event.message);
            snackbarStore.showErrorMessage(`AI 出错：${event.message}`);
            break;
        }
      },
    });
  } catch (e) {
    messageStore.failMessage(
      props.sessionId,
      aiMsg.id,
      (e as Error).message || "网络错误"
    );
    snackbarStore.showErrorMessage(`Chat SSE 失败：${(e as Error).message}`);
  } finally {
    // 防御：done 没收到时也终止 streaming 状态
    if (
      messageStore.findMessage(props.sessionId, aiMsg.id)?.streaming
    ) {
      messageStore.finishMessage(props.sessionId, aiMsg.id);
    }
  }
}

const onAi = (command: string) => {
  const ed = editor.value;
  if (!ed) return;
  const { from, to } = ed.state.selection;
  const selectionText = ed.state.doc.textBetween(from, to, "\n");
  emit("aiCommand", command, { selectionText });
  // 把光标定位到选区末尾，气泡插入到选区下方
  ed.chain().focus().setTextSelection(to).run();
  void runAiCommand(command, selectionText);
};
// 仅用于打标签显示（消除 AiBubble.vue 中要求的引用）
void COMMAND_LABELS;


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
  // 1. 删除 "/xxx" 占位文字
  ed.chain()
    .focus()
    .deleteRange({ from: slashFrom, to: cursorTo })
    .run();

  // 2. 按命令分发：格式块用 TipTap 内置 commands，AI 入口走 SSE
  switch (item.command) {
    case "h1":
      ed.chain().focus().toggleHeading({ level: 1 }).run();
      break;
    case "h2":
      ed.chain().focus().toggleHeading({ level: 2 }).run();
      break;
    case "h3":
      ed.chain().focus().toggleHeading({ level: 3 }).run();
      break;
    case "bullet-list":
      ed.chain().focus().toggleBulletList().run();
      break;
    case "ordered-list":
      ed.chain().focus().toggleOrderedList().run();
      break;
    case "code-block":
      ed.chain().focus().toggleCodeBlock().run();
      break;
    case "blockquote":
      ed.chain().focus().toggleBlockquote().run();
      break;
    case "hr":
      ed.chain().focus().setHorizontalRule().run();
      break;
    case "ask-ai":
      void runAiCommand("ask", "");
      break;
    case "task": {
      // F12: 提取 /task 后面的指令文本
      const taskInstruction = slashState.query.trim() || "";
      emit("taskCommand", taskInstruction);
      snackbarStore.showSuccessMessage(
        taskInstruction
          ? `编排任务已提交：${taskInstruction.slice(0, 30)}…`
          : "编排任务已提交"
      );
      break;
    }
    default:
      console.warn("[slash] 未知命令:", item.command);
  }
};

// Step 2 跨视图同步：editor 就绪时注册到 EditorBus，让浮窗能反向调
watch(
  () => editor.value,
  (ed) => {
    if (ed && props.tileId) editorBus.register(ed, props.tileId);
  },
  { immediate: true }
);

onBeforeUnmount(() => {
  editorBus.unregister(editor.value || undefined);
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
