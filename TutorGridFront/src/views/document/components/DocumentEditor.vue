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
import { AiBlock } from "../extensions/ai-block";
import {
  PLACEHOLDER_LABELS,
  makeAiBlockId,
} from "../extensions/ai-block-types";
import {
  resolveMockBlock,
  mockAgentProgress,
  mockRagResolution,
} from "../extensions/mock-ai-data";
import {
  parseQuizMarkdown,
  parseFlashcardMarkdown,
  markdownToSimpleHtml,
} from "../extensions/markdown-parsers";
import SlashCommandMenu from "../extensions/SlashCommandMenu.vue";
import type { SlashItem } from "../extensions/SlashCommandMenu.vue";
import {
  SLASH_ITEMS,
  filterSlashItems,
} from "../extensions/slash-command-items";
import { useOrchestratorStore } from "@/stores/orchestratorStore";
import { useWorkspaceStore } from "@/stores/workspaceStore";
import { useKnowledgeStore } from "@/stores/knowledgeStore";
import type { AgentArtifact, AgentData, AgentPhaseEvent } from "../extensions/ai-block-types";

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
const workspaceStore = useWorkspaceStore();
const knowledgeStore = useKnowledgeStore();

const COMMAND_TARGET_KIND: Record<string, "text" | "quiz" | "flashcard" | "agent"> = {
  "explain-selection": "text",
  "summarize-selection": "text",
  "rewrite-selection": "text",
  "continue-writing": "text",
  "ask": "text",
  "rag-query": "text",
  "generate-quiz": "quiz",
  "generate-flashcards": "flashcard",
  "do-task": "agent",
};

const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
  (e: "ready", editor: Editor): void;
  (e: "aiCommand", command: string, payload?: any): void;
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
    AiBlock,
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

const MOCK_PLACEHOLDER_DELAY_MS = 2200;
const MOCK_AGENT_STEP_INTERVAL_MS = 1600;

const persistSessionId = async (sessionId: string) => {
  if (!props.tileId || !sessionId) return;
  const tile = workspaceStore.findTile(props.tileId);
  if (!tile) return;
  if (tile.metadata?.sessionId === sessionId) return;
  await workspaceStore.setTileMetadata(props.tileId, { sessionId });
};

const currentSessionId = (): string => {
  if (!props.tileId) return "";
  const tile = workspaceStore.findTile(props.tileId);
  return tile?.metadata?.sessionId || "";
};

const runAiCommand = (command: string, selectionText: string) => {
  const ed = editor.value;
  if (!ed) return;
  const blockId = makeAiBlockId();
  const targetKind = COMMAND_TARGET_KIND[command] || "text";
  ed.chain()
    .focus()
    .insertAiBlock({
      id: blockId,
      kind: "placeholder",
      command,
      createdBy: "ai",
      data: { label: PLACEHOLDER_LABELS[command] || "AI 思考中" },
    })
    .run();

  if (command === "rag-query") {
    if (orchestratorStore.isLive) {
      runRagPipeline(blockId, selectionText).catch((err) => {
        console.warn("[rag] live pipeline failed, falling back to mock", err);
        applyMockRag(blockId, selectionText);
      });
    } else {
      applyMockRag(blockId, selectionText);
    }
    return;
  }

  if (orchestratorStore.isLive) {
    runLivePipeline(blockId, command, targetKind, selectionText).catch(
      (err) => {
        console.warn("[orchestrator] live pipeline failed, falling back to mock", err);
        runMockPipeline(blockId, command, selectionText);
      }
    );
  } else {
    runMockPipeline(blockId, command, selectionText);
  }
};

const applyMockRag = (blockId: string, question: string) => {
  const ed = editor.value;
  if (!ed) return;
  const m = mockRagResolution(question || "（请先选中要查询的问题）");
  setTimeout(() => {
    if (!editor.value || editor.value.isDestroyed) return;
    editor.value.commands.updateAiBlockById(blockId, {
      kind: "citation",
      data: {
        question: m.question,
        answer: m.answer,
        answerHtml: markdownToSimpleHtml(m.answer),
        courseName: "MetaAgent 默认课程（mock）",
        chunks: m.chunks,
      },
    });
  }, 1200);
};

const runRagPipeline = async (blockId: string, question: string) => {
  const ed = editor.value;
  if (!ed) return;
  if (!question.trim()) {
    ed.commands.updateAiBlockById(blockId, {
      kind: "text",
      data: { html: "<p>请先选中要查询的问题文本。</p>" },
    });
    return;
  }
  const courseId = await knowledgeStore.ensureDefaultCourse();
  const res = await orchestratorStore.knowledgeRagQuery({
    courseId,
    text: question,
    limit: 8,
  });
  const items: any[] = res?.items || [];
  const fileNameById = new Map<string, string>();
  knowledgeStore.files.forEach((f) => fileNameById.set(f.fileId, f.fileName));
  const chunks = items.map((it) => ({
    chunkId: it.chunkId || "",
    fileId: it.fileId || "",
    fileName: fileNameById.get(it.fileId) || it.fileName || "",
    content: (it.content || "").slice(0, 320),
    sourcePage: it.sourcePage || 0,
    sourceSection: it.sourceSection || "",
    score: typeof it.score === "number" ? it.score : it.rerankScore || 0,
  }));
  const answer = res?.answer || "（后端未返回答案）";
  ed.commands.updateAiBlockById(blockId, {
    kind: "citation",
    data: {
      question,
      answer,
      answerHtml: markdownToSimpleHtml(answer),
      courseId,
      courseName: knowledgeStore.courseName,
      chunks,
    },
  });
};

const runMockPipeline = (blockId: string, command: string, selectionText: string) => {
  setTimeout(() => {
    if (!editor.value || editor.value.isDestroyed) return;
    const resolved = resolveMockBlock({ command, selectionText });
    editor.value.commands.updateAiBlockById(blockId, {
      kind: resolved.kind,
      data: resolved.data,
    });
    if (resolved.kind === "agent") {
      runMockAgentTimeline(blockId, resolved.data);
    }
  }, MOCK_PLACEHOLDER_DELAY_MS);
};

const runMockAgentTimeline = (blockId: string, initialData: any) => {
  let step = 0;
  let current = initialData;
  const tick = () => {
    if (!editor.value || editor.value.isDestroyed) return;
    const next = mockAgentProgress(current, step);
    editor.value.commands.updateAiBlockById(blockId, { data: next });
    current = next;
    step += 1;
    if (next.done) return;
    if (next.awaitingPrompt) return;
    setTimeout(tick, MOCK_AGENT_STEP_INTERVAL_MS);
  };
  setTimeout(tick, MOCK_AGENT_STEP_INTERVAL_MS);
};

const runLivePipeline = async (
  blockId: string,
  command: string,
  targetKind: "text" | "quiz" | "flashcard" | "agent",
  selectionText: string
) => {
  const ed = editor.value;
  if (!ed) return;
  const documentText = ed.getText();
  const existingSessionId = currentSessionId();
  const workspace = workspaceStore.root || undefined;

  const { sessionId, isNew } = await orchestratorStore.runTipTapCommand({
    command,
    selectionText,
    documentText,
    sessionId: existingSessionId || undefined,
    workspace,
  });

  if (!sessionId) {
    throw new Error("tiptap.command 返回缺少 sessionId");
  }

  ed.commands.updateAiBlockById(blockId, { sessionId });
  if (isNew || !existingSessionId) {
    await persistSessionId(sessionId);
  }

  if (targetKind === "agent") {
    await streamAgentLifecycle(blockId, sessionId, selectionText);
  } else {
    await streamTextLikeBlock(blockId, command, targetKind, sessionId);
  }
};

const STREAM_IDLE_FALLBACK_MS = 30_000;

const streamTextLikeBlock = (
  blockId: string,
  command: string,
  targetKind: "text" | "quiz" | "flashcard",
  sessionId: string
): Promise<void> => {
  const ed = editor.value;
  if (!ed) return Promise.resolve();
  let messageId = "";
  let accumulated = "";
  let finalized = false;
  let watchdog: ReturnType<typeof setTimeout> | null = null;

  return new Promise<void>((resolve) => {
    const settle = () => {
      if (finalized) return;
      finalized = true;
      if (watchdog) clearTimeout(watchdog);
      unsub();
      resolve();
    };
    const armWatchdog = () => {
      if (watchdog) clearTimeout(watchdog);
      watchdog = setTimeout(() => {
        if (finalized) return;
        if (accumulated.length > 0) {
          applyTextLikeFinal(blockId, command, targetKind, accumulated);
          settle();
          return;
        }
        console.warn("[orchestrator] no events for 30s, falling back to mock for", command);
        const resolved = resolveMockBlock({ command, selectionText: "" });
        if (editor.value && !editor.value.isDestroyed) {
          editor.value.commands.updateAiBlockById(blockId, {
            kind: resolved.kind,
            data: resolved.data,
          });
        }
        settle();
      }, STREAM_IDLE_FALLBACK_MS);
    };
    armWatchdog();
    const unsub = orchestratorStore.subscribeSession(sessionId, (event, payload) => {
      const cur = editor.value;
      if (!cur || cur.isDestroyed) {
        settle();
        return;
      }
      if (event === "orchestrator.session.message.started") {
        if (!messageId) messageId = payload?.messageId || "";
        armWatchdog();
        return;
      }
      if (
        event === "orchestrator.session.message.delta" &&
        (!messageId || payload?.messageId === messageId)
      ) {
        if (!messageId) messageId = payload?.messageId || "";
        accumulated += payload?.delta || "";
        cur.commands.updateAiBlockById(blockId, {
          data: {
            label: PLACEHOLDER_LABELS[command] || "AI 思考中",
            stream: accumulated,
          },
        });
        armWatchdog();
        return;
      }
      if (
        event === "orchestrator.session.message.completed" &&
        (!messageId || payload?.messageId === messageId)
      ) {
        const finalContent = payload?.content || accumulated;
        applyTextLikeFinal(blockId, command, targetKind, finalContent);
        settle();
        return;
      }
      if (event === "orchestrator.session.failed") {
        cur.commands.updateAiBlockById(blockId, {
          kind: "text",
          data: {
            html: `<p>任务失败：${
              payload?.message || payload?.error || "未知错误"
            }</p>`,
          },
        });
        settle();
        return;
      }
      if (event === "orchestrator.session.completed" && accumulated && !finalized) {
        applyTextLikeFinal(blockId, command, targetKind, accumulated);
        settle();
      }
    });
  });
};

const applyTextLikeFinal = (
  blockId: string,
  command: string,
  targetKind: "text" | "quiz" | "flashcard",
  content: string
) => {
  const ed = editor.value;
  if (!ed) return;
  if (targetKind === "quiz") {
    const questions = parseQuizMarkdown(content);
    if (questions.length > 0) {
      ed.commands.updateAiBlockById(blockId, {
        kind: "quiz",
        data: { questions, markdown: content },
      });
      return;
    }
    ed.commands.updateAiBlockById(blockId, {
      kind: "text",
      data: {
        html: markdownToSimpleHtml(content),
        markdown: content,
      },
      command,
    });
    return;
  }
  if (targetKind === "flashcard") {
    const cards = parseFlashcardMarkdown(content);
    if (cards.length > 0) {
      ed.commands.updateAiBlockById(blockId, {
        kind: "flashcard",
        data: { cards, markdown: content },
      });
      return;
    }
    ed.commands.updateAiBlockById(blockId, {
      kind: "text",
      data: {
        html: markdownToSimpleHtml(content),
        markdown: content,
      },
      command,
    });
    return;
  }
  ed.commands.updateAiBlockById(blockId, {
    kind: "text",
    data: {
      html: markdownToSimpleHtml(content),
      markdown: content,
    },
  });
};

const streamAgentLifecycle = (
  blockId: string,
  sessionId: string,
  selectionText: string
): Promise<void> => {
  const ed = editor.value;
  if (!ed) return Promise.resolve();
  const initialAgent: AgentData = {
    task: selectionText
      ? `基于选区执行：${selectionText.slice(0, 40)}`
      : "执行用户任务",
    currentPhase: "starting",
    history: [
      { phase: "created", message: "会话已创建", timestamp: Date.now() },
    ],
    awaitingPrompt: "",
    artifacts: [],
    finalAnswer: "",
    done: false,
  };
  ed.commands.updateAiBlockById(blockId, {
    kind: "agent",
    sessionId,
    data: initialAgent,
  });

  let messageId = "";

  const getCurrentAgentData = (): AgentData => {
    const ed2 = editor.value;
    if (!ed2) return initialAgent;
    let data: AgentData = initialAgent;
    ed2.state.doc.descendants((node) => {
      if (node.type.name === "aiBlock" && node.attrs.id === blockId) {
        data = (node.attrs.data as AgentData) || initialAgent;
        return false;
      }
      return true;
    });
    return data;
  };

  const pushPhase = (phase: string, message?: string) => {
    const cur = getCurrentAgentData();
    const last = cur.history?.[cur.history.length - 1];
    const next: AgentPhaseEvent[] = [...(cur.history || [])];
    if (!last || last.phase !== phase) {
      next.push({ phase, message: message || "", timestamp: Date.now() });
    } else if (message && last.message !== message) {
      next.push({ phase, message, timestamp: Date.now() });
    }
    ed.commands.updateAiBlockById(blockId, {
      data: { ...cur, currentPhase: phase, history: next },
    });
  };

  const setData = (patch: Partial<AgentData>) => {
    const cur = getCurrentAgentData();
    ed.commands.updateAiBlockById(blockId, { data: { ...cur, ...patch } });
  };

  return new Promise<void>((resolve) => {
    const unsub = orchestratorStore.subscribeSession(sessionId, async (event, payload) => {
      if (!editor.value || editor.value.isDestroyed) {
        unsub();
        resolve();
        return;
      }
      switch (event) {
        case "orchestrator.session.phase":
          pushPhase(payload?.phase || "planning", payload?.message);
          break;
        case "orchestrator.session.summary":
          if (payload?.message) pushPhase(getCurrentAgentData().currentPhase || "planning", payload.message);
          break;
        case "orchestrator.session.await_user":
          setData({
            awaitingPrompt: payload?.message || "请提供进一步信息",
            currentPhase: "awaiting_user",
          });
          break;
        case "orchestrator.session.message.started":
          if (!messageId) messageId = payload?.messageId || "";
          break;
        case "orchestrator.session.message.delta":
          if (
            (!messageId || payload?.messageId === messageId) &&
            payload?.delta
          ) {
            if (!messageId) messageId = payload?.messageId || "";
            const cur = getCurrentAgentData();
            setData({
              finalAnswer: (cur.finalAnswer || "") + payload.delta,
            });
          }
          break;
        case "orchestrator.session.message.completed":
          if (!messageId || payload?.messageId === messageId) {
            setData({ finalAnswer: payload?.content || getCurrentAgentData().finalAnswer || "" });
          }
          break;
        case "orchestrator.session.artifact.created":
        case "orchestrator.session.artifact.updated":
        case "orchestrator.session.artifact_summary":
          // refresh full artifact list lazily
          try {
            const res = await orchestratorStore.fetchSessionArtifacts(sessionId);
            const items: AgentArtifact[] = (res?.items || []).map((it: any) => ({
              path: it.path,
              title: it.path?.split(/[\\/]/).pop() || it.path,
              summary: it.summary || "",
            }));
            setData({ artifacts: items });
          } catch {
            /* ignore */
          }
          break;
        case "orchestrator.session.completed":
          pushPhase("completed", payload?.summary || "任务结束");
          setData({ done: true, currentPhase: "completed" });
          unsub();
          resolve();
          break;
        case "orchestrator.session.failed":
          pushPhase("failed", payload?.message || payload?.error || "失败");
          setData({ done: true, currentPhase: "failed" });
          unsub();
          resolve();
          break;
      }
    });
  });
};

const onAi = (command: string) => {
  const ed = editor.value;
  if (!ed) return;
  const { from, to } = ed.state.selection;
  const selectionText = ed.state.doc.textBetween(from, to, "\n");
  emit("aiCommand", command, { selectionText });
  if (command === "send-to-chat") return;
  ed.chain().focus().setTextSelection(to).run();
  runAiCommand(command, selectionText);
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
  runAiCommand(item.command, "");
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
