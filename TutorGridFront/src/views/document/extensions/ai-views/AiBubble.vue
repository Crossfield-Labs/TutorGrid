<!--
  AI 气泡节点视图 (F07)
  - 用户气泡：右侧头像 + 灰底
  - AI 气泡：左侧头像 + 磨砂底 + 流式打字效果
  - 内容来自 messageStore，实时响应 SSE delta
-->
<template>
  <NodeViewWrapper class="ai-bubble-wrapper" data-drag-handle>
    <!-- 用户气泡（Q）-->
    <div v-if="userMessage" class="bubble-row bubble-row--user">
      <div class="bubble-content bubble-content--user">
        <div class="bubble-meta">
          <v-icon size="11" icon="mdi-account-outline" class="mr-1" />
          <span>你</span>
          <span v-if="commandLabel" class="ml-2">· {{ commandLabel }}</span>
        </div>
        <div class="bubble-text bubble-text--user">
          {{ userMessage.content }}
        </div>
      </div>
      <v-avatar size="32" class="bubble-avatar bubble-avatar--user">
        <v-img :src="avatarUser" alt="user" />
      </v-avatar>
    </div>

    <!-- AI 气泡（A）-->
    <div class="bubble-row bubble-row--ai">
      <v-avatar size="32" class="bubble-avatar bubble-avatar--ai">
        <v-img :src="avatarAssistant" alt="AI" />
      </v-avatar>
      <div class="bubble-content bubble-content--ai">
        <div class="bubble-meta">
          <v-icon size="11" icon="mdi-sparkles" color="primary" class="mr-1" />
          <span>AI</span>
          <span v-if="aiMessage?.streaming" class="ml-2 streaming-dot">
            正在生成
            <span class="dot-anim">…</span>
          </span>
          <v-spacer />
          <!-- Step 2 跨视图同步：把这个 AI 段落放到 Chat 浮窗里继续讨论 -->
          <v-tooltip
            v-if="!aiMessage?.streaming && aiMessage?.content"
            location="top"
            text="在 Chat 中讨论"
          >
            <template #activator="{ props: tipProps }">
              <v-btn
                v-bind="tipProps"
                size="x-small"
                icon="mdi-comment-outline"
                variant="text"
                density="comfortable"
                @click="onDiscussInChat"
              />
            </template>
          </v-tooltip>
          <v-tooltip v-if="!aiMessage?.streaming" location="top" text="删除气泡">
            <template #activator="{ props: tipProps }">
              <v-btn
                v-bind="tipProps"
                size="x-small"
                icon="mdi-close"
                variant="text"
                density="comfortable"
                @click="onRemove"
              />
            </template>
          </v-tooltip>
        </div>

        <!-- 工具调用提示 -->
        <div
          v-if="toolsUsed.length"
          class="bubble-tool-strip"
        >
          <v-chip
            v-for="t in toolsUsed"
            :key="t"
            size="x-small"
            variant="tonal"
            :color="toolColor(t)"
            class="mr-1"
          >
            <v-icon :icon="toolIcon(t)" size="12" class="mr-1" />
            {{ t }}
          </v-chip>
        </div>

        <!-- 主内容（markdown 渲染）-->
        <div
          v-if="aiMessage?.content"
          class="bubble-text bubble-text--ai markdown-body"
          v-html="renderedContent"
        />
        <div
          v-else-if="aiMessage?.streaming"
          class="bubble-text bubble-text--ai text-medium-emphasis"
        >
          <v-progress-circular
            indeterminate
            size="14"
            width="2"
            color="primary"
            class="mr-2"
          />
          AI 正在思考…
        </div>
        <div
          v-else-if="aiMessage?.errored"
          class="bubble-text bubble-text--ai text-error"
        >
          {{ aiMessage.content || "请求失败" }}
        </div>

        <!-- 引用磁贴入口（如果有 citation 会在右侧 TileGrid 自动出现 CitationTile）-->
        <div v-if="citations.length" class="bubble-citation-hint">
          <v-icon size="13" icon="mdi-book-open-variant-outline" />
          引用 {{ citations.length }} 段课程资料 · 见右侧磁贴
        </div>
      </div>
    </div>
  </NodeViewWrapper>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { NodeViewWrapper, nodeViewProps } from "@tiptap/vue-3";
import { useMessageStore } from "@/stores/messageStore";
import { useChatMessageStore } from "@/stores/chatMessageStore";
import { useChatSessionStore } from "@/stores/chatSessionStore";
import { useSnackbarStore } from "@/stores/snackbarStore";
import { renderMarkdown, postProcessLinks } from "@/lib/markdown";
import avatarAssistant from "@/assets/images/avatars/avatar_assistant.jpg";
import avatarUser from "@/assets/images/avatars/avatar_user.jpg";

const props = defineProps(nodeViewProps);

const messageStore = useMessageStore();
const chatMsgStore = useChatMessageStore();
const chatSession = useChatSessionStore();
const snackbarStore = useSnackbarStore();

const sessionId = computed(() => (props.node.attrs.sessionId as string) || "");
const userMessageId = computed(
  () => (props.node.attrs.userMessageId as string) || ""
);
const aiMessageId = computed(
  () => (props.node.attrs.aiMessageId as string) || ""
);
const command = computed(() => (props.node.attrs.command as string) || "");

const userMessage = computed(() =>
  userMessageId.value
    ? messageStore.findMessage(sessionId.value, userMessageId.value)
    : null
);
const aiMessage = computed(() =>
  aiMessageId.value
    ? messageStore.findMessage(sessionId.value, aiMessageId.value)
    : null
);

const renderedContent = computed(() => {
  const text = aiMessage.value?.content ?? "";
  if (!text) return "";
  return postProcessLinks(renderMarkdown(text));
});

const toolsUsed = computed(() => aiMessage.value?.metadata?.toolsUsed ?? []);
const citations = computed(() => aiMessage.value?.metadata?.citations ?? []);

const COMMAND_LABELS: Record<string, string> = {
  "explain-selection": "讲解",
  "summarize-selection": "总结",
  "rewrite-selection": "改写",
  "continue-writing": "续写",
  "rag-query": "问知识库",
  "do-task": "执行任务",
  ask: "提问",
};
const commandLabel = computed(() => COMMAND_LABELS[command.value] || "");

const toolColor = (t: string) => {
  if (t.includes("rag")) return "success";
  if (t.includes("tavily")) return "info";
  return "grey";
};
const toolIcon = (t: string) => {
  if (t.includes("rag")) return "mdi-bookshelf";
  if (t.includes("tavily")) return "mdi-web";
  return "mdi-tools";
};

const onRemove = () => {
  if (typeof props.deleteNode === "function") {
    props.deleteNode();
  }
};

// Step 2 跨视图同步：把当前 AI 段落作为引用消息插入到当前 Chat 浮窗 session
const onDiscussInChat = () => {
  const text = aiMessage.value?.content || "";
  if (!text) return;
  const targetSessionId = chatSession.currentSessionId;
  if (!targetSessionId) {
    snackbarStore.showWarningMessage("当前没有活跃的 Chat 会话");
    return;
  }
  const excerpt = text.length > 200 ? text.slice(0, 200) + "…" : text;
  chatMsgStore.pushQuoteFromDocument(
    targetSessionId,
    `> 文档段落（AI 共做产出）\n${excerpt}\n\n请帮我继续讨论这一段。`,
    aiMessageId.value || "doc-bubble"
  );
  snackbarStore.showSuccessMessage("已加入当前会话，去 Chat 浮窗继续");
};
</script>

<style scoped lang="scss">
.ai-bubble-wrapper {
  margin: 14px 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bubble-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;

  &--user {
    flex-direction: row-reverse;
  }
}

.bubble-avatar {
  flex-shrink: 0;
  margin-top: 2px;
}

.bubble-content {
  max-width: 86%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bubble-meta {
  display: flex;
  align-items: center;
  font-size: 11px;
  color: rgba(15, 23, 42, 0.55);
  font-weight: 500;
}

.bubble-text {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.65;
  word-break: break-word;

  &--user {
    background: rgba(74, 85, 104, 0.92);
    color: #f3f4f6;
    border-top-right-radius: 4px;
  }

  &--ai {
    background: rgba(255, 255, 255, 0.65);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(194, 199, 209, 0.5);
    border-top-left-radius: 4px;
    color: #1e293b;
  }
}

.bubble-tool-strip {
  display: flex;
  flex-wrap: wrap;
  margin-bottom: 4px;
}

.bubble-citation-hint {
  margin-top: 6px;
  font-size: 11px;
  color: rgba(15, 23, 42, 0.5);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.streaming-dot {
  font-size: 10px;
  color: rgba(15, 23, 42, 0.5);
}

.dot-anim {
  animation: blink 1.2s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 1; }
}

// markdown 内置样式
.markdown-body :deep(p) {
  margin: 0 0 0.5em;
  &:last-child { margin-bottom: 0; }
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

// 暗色主题
:global(.v-theme--dark) .bubble-text--ai {
  background: rgba(45, 45, 50, 0.6);
  border-color: rgba(255, 255, 255, 0.1);
  color: #e2e8f0;
}
:global(.v-theme--dark) .bubble-meta {
  color: rgba(226, 232, 240, 0.6);
}
:global(.v-theme--dark) .markdown-body :deep(code) {
  background: rgba(255, 255, 255, 0.1);
}
</style>
