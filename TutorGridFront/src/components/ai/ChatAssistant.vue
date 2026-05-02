<!--
  F11: Chat 独立面板
  - 右下角浮动按钮 → 展开为右侧抽屉
  - 消费统一 messageStore
  - Chat SSE 流式响应
  - renderIn 含 'chat' 的消息在此渲染
-->
<template>
  <!-- 浮动触发按钮 -->
  <v-btn
    class="chat-fab"
    :class="{ 'fab-active': drawer }"
    size="50"
    color="primary"
    rounded="lg"
    elevation="8"
    @click="drawer = !drawer"
  >
    <v-icon size="28">
      {{ drawer ? 'mdi-close' : 'mdi-chat-outline' }}
    </v-icon>
    <v-tooltip activator="parent" location="left" text="智格生境 · AI 对话" />
  </v-btn>

  <!-- 右侧抽屉 -->
  <v-navigation-drawer
    v-model="drawer"
    location="right"
    temporary
    width="420"
    class="chat-drawer"
    :touchless="false"
  >
    <div class="chat-drawer-inner d-flex flex-column fill-height">
      <!-- 标题栏 -->
      <div class="chat-header pa-3">
        <div class="d-flex align-center">
          <v-avatar size="36" class="mr-2">
            <v-img :src="avatarAssistant" alt="AI" />
          </v-avatar>
          <div class="d-flex flex-column flex-fill">
            <span class="text-body-2 font-weight-bold">智格生境 · AI 对话</span>
            <span class="text-caption text-medium-emphasis">
              {{ sessionLabel }}
            </span>
          </div>
          <v-tooltip location="bottom" text="新建会话">
            <template #activator="{ props: tipProps }">
              <v-btn
                v-bind="tipProps"
                icon="mdi-plus"
                variant="text"
                size="small"
                @click.stop="onNewSession"
              />
            </template>
          </v-tooltip>
        </div>
      </div>
      <v-divider />

      <!-- 消息列表 -->
      <div class="chat-messages flex-fill">
        <div v-if="messages.length" ref="msgContainer" class="message-list pa-2">
          <template v-for="message in messages" :key="message.id">
            <!-- 用户消息 -->
            <div v-if="message.role === 'user'" class="msg-row user-row mb-2">
              <v-card class="msg-bubble user-bubble" theme="dark">
                <v-card-text class="pa-2">
                  <div
                    v-if="message.metadata?.origin === 'document' || message.metadata?.command"
                    class="text-caption opacity-70 mb-1 d-flex align-center"
                  >
                    <v-icon size="11" :icon="message.metadata?.origin === 'document' ? 'mdi-file-document-outline' : 'mdi-comment-outline'" class="mr-1" />
                    {{ message.metadata?.origin === 'document' ? '文档' : 'Chat' }}
                    <span v-if="message.metadata?.command" class="ml-1">· {{ message.metadata.command }}</span>
                  </div>
                  <b>{{ message.content }}</b>
                </v-card-text>
              </v-card>
              <v-avatar size="28" class="ml-1">
                <v-img :src="avatarUser" alt="user" />
              </v-avatar>
            </div>

            <!-- AI 消息 -->
            <div v-else class="msg-row ai-row mb-2">
              <v-avatar size="28" class="mr-1">
                <v-img :src="avatarAssistant" alt="AI" />
              </v-avatar>
              <v-card class="msg-bubble ai-bubble flex-fill">
                <v-card-text class="pa-2">
                  <!-- 工具调用标签 -->
                  <div v-if="message.metadata?.toolsUsed?.length" class="mb-1">
                    <v-chip
                      v-for="t in message.metadata.toolsUsed"
                      :key="t"
                      size="x-small"
                      variant="tonal"
                      :color="t.includes('rag') ? 'success' : 'info'"
                      class="mr-1 mb-1"
                    >
                      <v-icon :icon="t.includes('rag') ? 'mdi-bookshelf' : 'mdi-web'" size="11" class="mr-1" />
                      {{ t }}
                    </v-chip>
                  </div>

                  <div v-if="message.content" class="markdown-body" v-html="renderAi(message.content)" />

                  <div v-else-if="message.streaming" class="d-flex align-center text-medium-emphasis">
                    <v-progress-circular indeterminate size="14" width="2" color="primary" class="mr-2" />
                    AI 正在思考…
                  </div>
                </v-card-text>
              </v-card>
            </div>
          </template>
        </div>

        <!-- 空状态 -->
        <div v-else class="empty-state d-flex flex-column align-center justify-center fill-height text-grey">
          <v-icon icon="mdi-message-text-outline" size="48" class="mb-3" />
          <div class="text-h6 text-medium-emphasis">开始对话</div>
          <div class="text-caption text-disabled mt-1 text-center px-4">
            输入问题，AI 会从知识库 / 联网检索为你解答
          </div>
          <div class="text-caption text-disabled mt-3">
            {{ sessionLabel }}
          </div>
        </div>
      </div>
      <v-divider />

      <!-- 输入区 -->
      <div class="chat-input pa-2">
        <div class="d-flex align-end ga-2">
          <v-textarea
            v-model="userMessage"
            color="primary"
            variant="solo-filled"
            placeholder="问一下..."
            hide-details
            rows="1"
            auto-grow
            :max-rows="5"
            :disabled="isLoading"
            density="compact"
            class="flex-fill"
            @keydown="handleKeydown"
          />
          <v-btn
            color="primary"
            variant="elevated"
            icon="mdi-send"
            size="42"
            :loading="isLoading"
            :disabled="isLoading || !userMessage.trim()"
            @click="sendMessage"
          />
        </div>
      </div>
    </div>
  </v-navigation-drawer>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { useSnackbarStore } from "@/stores/snackbarStore";
import { useMessageStore } from "@/stores/messageStore";
import { useChatSessionStore, makeSessionId } from "@/stores/chatSessionStore";
import { useWorkspaceStore } from "@/stores/workspaceStore";
import { streamChat } from "@/lib/chat-sse";
import { renderMarkdown, postProcessLinks } from "@/lib/markdown";
import { scrollToBottom } from "@/utils/common";
import avatarAssistant from "@/assets/images/avatars/avatar_assistant.jpg";
import avatarUser from "@/assets/images/avatars/avatar_user.jpg";

const snackbarStore = useSnackbarStore();
const messageStore = useMessageStore();
const chatSession = useChatSessionStore();
const workspaceStore = useWorkspaceStore();

// ── drawer ──
const drawer = ref(false);

// 暴露打开/关闭方法供外部调用
defineExpose({ open: () => (drawer.value = true), close: () => (drawer.value = false), toggle: () => (drawer.value = !drawer.value) });

// ── 消息 ──
const userMessage = ref("");
const isLoading = ref(false);
const msgContainer = ref<HTMLElement | null>(null);

const sessionId = computed(() => chatSession.currentSessionId);
const messages = computed(() => messageStore.getSessionMessages(sessionId.value));

const renderAi = (text: string) => postProcessLinks(renderMarkdown(text));

const sendMessage = async () => {
  const text = userMessage.value.trim();
  if (!text) return;
  if (!sessionId.value) {
    snackbarStore.showErrorMessage("当前没有活跃 session");
    return;
  }

  messageStore.addUserMessage(sessionId.value, text, "chat");
  const aiMsg = messageStore.startAiMessage(sessionId.value, "chat");

  userMessage.value = "";
  isLoading.value = true;

  try {
    await streamChat({
      payload: {
        session_id: sessionId.value,
        message: text,
        course_id: chatSession.courseId || undefined,
        tools: ["rag", "tavily"],
        context: chatSession.currentDocId ? { doc_id: chatSession.currentDocId } : undefined,
      },
      onEvent: (event) => {
        switch (event.type) {
          case "tool_call":
            messageStore.addToolUsed(sessionId.value, aiMsg.id, event.tool);
            break;
          case "tool_result":
            if (event.citations?.length) {
              messageStore.addCitations(sessionId.value, aiMsg.id, event.citations);
            }
            if (event.results?.length) {
              messageStore.addSearchResults(sessionId.value, aiMsg.id, event.results);
            }
            break;
          case "delta":
            messageStore.appendDelta(sessionId.value, aiMsg.id, event.content);
            break;
          case "done":
            messageStore.finishMessage(sessionId.value, aiMsg.id);
            break;
          case "error":
            messageStore.failMessage(sessionId.value, aiMsg.id, event.message);
            snackbarStore.showErrorMessage(`AI 出错：${event.message}`);
            break;
        }
      },
    });
  } catch (e) {
    messageStore.failMessage(sessionId.value, aiMsg.id, (e as Error).message || "网络错误");
    snackbarStore.showErrorMessage(`Chat SSE 失败：${(e as Error).message}`);
  } finally {
    if (messageStore.findMessage(sessionId.value, aiMsg.id)?.streaming) {
      messageStore.finishMessage(sessionId.value, aiMsg.id);
    }
    isLoading.value = false;
  }
};

// 新消息自动滚动
watch(
  messages,
  () => {
    nextTick(() => scrollToBottom(msgContainer.value));
  },
  { deep: true }
);

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === "Enter" && (e.altKey || e.shiftKey)) {
    e.preventDefault();
    userMessage.value += "\n";
  } else if (e.key === "Enter") {
    e.preventDefault();
    sendMessage();
  }
};

const sessionLabel = computed(() => {
  if (!chatSession.currentDocId) return "全局会话";
  return `文档会话 · ${chatSession.currentDocId.slice(0, 8)}`;
});

const onNewSession = async () => {
  const newId = makeSessionId();
  const docId = chatSession.currentDocId;
  if (docId) {
    const tile = workspaceStore.findTile(docId);
    if (tile) {
      try {
        await workspaceStore.setTileMetadata(tile.id, { sessionId: newId });
      } catch (e) {
        console.error("[chat] 新会话持久化失败", e);
      }
    }
  }
  chatSession.setSession(newId, docId);
  snackbarStore.showSuccessMessage("已开始新会话");
};
</script>

<style scoped lang="scss">
// 浮动触发按钮
.chat-fab {
  z-index: 998;
  position: fixed;
  bottom: 100px;
  right: 10px;
  transition: all 0.3s ease;

  &.fab-active {
    right: 430px; // 抽屉宽度 + 10px 间距
  }
}

// 抽屉
.chat-drawer {
  :deep(.v-navigation-drawer__content) {
    display: flex;
    flex-direction: column;
    height: 100%;
  }
}

.chat-drawer-inner {
  height: 100%;
  overflow: hidden;
}

.chat-header {
  flex-shrink: 0;
}

// 消息区
.chat-messages {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;

  scrollbar-width: thin;
  scrollbar-color: rgba(0, 0, 0, 0.2) transparent;

  &::-webkit-scrollbar { width: 6px; }
  &::-webkit-scrollbar-track { background: transparent; }
  &::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.2);
    border-radius: 3px;
    &:hover { background: rgba(0, 0, 0, 0.35); }
  }
}

.empty-state {
  min-height: 300px;
}

// 消息行
.msg-row {
  display: flex;
  align-items: flex-start;
}

.user-row {
  justify-content: flex-end;
}

.ai-row {
  justify-content: flex-start;
}

.msg-bubble {
  max-width: 80%;
}

.user-bubble {
  background: linear-gradient(135deg, #4a5568 0%, #2d3748 100%) !important;
}

.ai-bubble {
  background: rgba(255, 255, 255, 0.95) !important;
}

// 输入区
.chat-input {
  flex-shrink: 0;
}

// 响应式：窄屏全宽
@media (max-width: 480px) {
  .chat-drawer {
    width: 100% !important;
  }
  .chat-fab.fab-active {
    right: 10px;
  }
}

// Markdown 渲染
.markdown-body :deep(p) {
  margin: 0 0 0.5em;
  font-size: 13px;
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
</style>
