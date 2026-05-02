<!--
* @Component: ChatAssistant
* @Description: AI 对话浮窗 (基于旧项目 J.K. Yang 的版本，接入 SSE + messageStore)
*
* 设计参考：作者原版 + 我们后端 (POST /api/chat/stream)
* 保留：浮窗布局 / 用户头像气泡 / AI markdown 卡片 / perfect-scrollbar 固定高度滚动
* 替换：OpenAI 直连 → 我们的 SSE 后端，自管 messages → 共享 messageStore
-->
<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { useDisplay } from "vuetify";
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
const { xs } = useDisplay();

const userMessage = ref("");
const isLoading = ref(false);
const inputRow = ref(1);
const dialog = ref(false);

const sessionId = computed(() => chatSession.currentSessionId);
// 解耦文档/Chat：浮窗只显示 origin === 'chat' 的消息（或 origin 缺失的旧数据，兼容）
// 文档内 AI 气泡（origin === 'document'）由 TipTap 节点单独渲染，不出现在浮窗
const messages = computed(() =>
  messageStore
    .getSessionMessages(sessionId.value)
    .filter((m) => m.metadata?.origin !== "document")
);

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
        context: chatSession.currentDocId
          ? { doc_id: chatSession.currentDocId }
          : undefined,
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
    messageStore.failMessage(
      sessionId.value,
      aiMsg.id,
      (e as Error).message || "网络错误"
    );
    snackbarStore.showErrorMessage(`Chat SSE 失败：${(e as Error).message}`);
  } finally {
    if (messageStore.findMessage(sessionId.value, aiMsg.id)?.streaming) {
      messageStore.finishMessage(sessionId.value, aiMsg.id);
    }
    isLoading.value = false;
  }
};

watch(
  messages,
  () => {
    nextTick(() => scrollToBottom(document.querySelector(".message-container")));
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

const onConfigClick = () => {
  snackbarStore.showInfoMessage("系统配置功能将在 F16 安装向导中实现");
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

<template>
  <v-btn size="50" @click="dialog = !dialog">
    <v-icon size="30">mdi-chat-outline</v-icon>
    <v-tooltip activator="parent" location="left" text="AI 对话" />
  </v-btn>

  <teleport to="body">
    <transition name="slide-y">
      <v-card
        v-if="dialog"
        class="dialog-bottom d-flex flex-column"
        :width="xs ? '100%' : '600px'"
        height="500px"
      >
        <v-card-title>
          <span class="flex-fill d-inline-flex align-center">
            <v-avatar size="40" class="mr-2">
              <v-img :src="avatarAssistant" alt="AI" />
            </v-avatar>
            <div class="d-flex flex-column">
              <span>智格生境 · AI 对话</span>
              <span class="text-caption text-medium-emphasis">
                {{ sessionLabel }}
              </span>
            </div>
          </span>

          <v-spacer />
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
          <v-btn icon variant="text" @click.stop="dialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-divider />

        <v-card-text class="pa-0">
          <div
            v-if="messages.length > 0"
            class="message-container"
          >
            <template v-for="message in messages" :key="message.id">
              <!-- 用户消息 -->
              <div v-if="message.role === 'user'">
                <div class="pa-2 user-message">
                  <v-avatar class="ml-2" rounded="sm" variant="elevated">
                    <v-img :src="avatarUser" alt="user" />
                  </v-avatar>
                  <v-card class="gradient-gray text-pre-wrap" theme="dark">
                    <v-card-text>
                      <div
                        v-if="
                          message.metadata?.origin === 'document' ||
                          message.metadata?.command
                        "
                        class="text-caption opacity-80 mb-1 d-flex align-center"
                      >
                        <v-icon
                          size="11"
                          :icon="
                            message.metadata?.origin === 'document'
                              ? 'mdi-file-document-outline'
                              : 'mdi-comment-outline'
                          "
                          class="mr-1"
                        />
                        {{
                          message.metadata?.origin === "document"
                            ? "文档"
                            : "Chat"
                        }}
                        <span v-if="message.metadata?.command" class="ml-2">
                          · {{ message.metadata.command }}
                        </span>
                      </div>
                      <b>{{ message.content }}</b>
                    </v-card-text>
                  </v-card>
                </div>
              </div>

              <!-- AI 消息 -->
              <div v-else>
                <div class="pa-2 assistant-message">
                  <v-avatar
                    class="d-none d-md-block mr-2"
                    rounded="sm"
                    variant="elevated"
                  >
                    <v-img :src="avatarAssistant" alt="AI" />
                  </v-avatar>
                  <v-card class="ai-card">
                    <div class="px-3 py-2">
                      <!-- 工具调用标签 -->
                      <div
                        v-if="message.metadata?.toolsUsed?.length"
                        class="mb-2"
                      >
                        <v-chip
                          v-for="t in message.metadata.toolsUsed"
                          :key="t"
                          size="x-small"
                          variant="tonal"
                          :color="t.includes('rag') ? 'success' : 'info'"
                          class="mr-1"
                        >
                          <v-icon
                            :icon="
                              t.includes('rag') ? 'mdi-bookshelf' : 'mdi-web'
                            "
                            size="12"
                            class="mr-1"
                          />
                          {{ t }}
                        </v-chip>
                      </div>

                      <div
                        v-if="message.content"
                        class="markdown-body font-1"
                        v-html="renderAi(message.content)"
                      ></div>
                      <div
                        v-else-if="message.streaming"
                        class="d-flex align-center text-medium-emphasis"
                      >
                        <v-progress-circular
                          indeterminate
                          size="14"
                          width="2"
                          color="primary"
                          class="mr-2"
                        ></v-progress-circular>
                        AI 正在思考…
                      </div>
                    </div>
                  </v-card>
                </div>
              </div>
            </template>
          </div>

          <div v-else class="no-message-container">
            <v-icon icon="mdi-message-text-outline" size="48" color="grey" />
            <h1 class="text-h6 text-medium-emphasis mt-3">开始对话</h1>
            <div class="text-caption text-disabled mt-1">
              输入问题，AI 会从知识库 / 联网检索为你解答
            </div>
            <div class="text-caption text-disabled mt-3">
              {{ sessionLabel }}
            </div>
          </div>
        </v-card-text>
        <v-divider />

        <v-sheet
          color="transparent"
          elevation="0"
          class="d-flex align-end justify-center pa-2"
        >
          <v-btn
            class="mb-1"
            variant="elevated"
            size="42"
            icon
            :disabled="isLoading"
            @click="onConfigClick"
          >
            <v-icon size="24" class="text-primary">mdi-cog-outline</v-icon>
            <v-tooltip activator="parent" location="top" text="系统配置" />
          </v-btn>

          <v-textarea
            class="mx-2"
            color="primary"
            type="text"
            clearable
            variant="solo"
            v-model="userMessage"
            placeholder="问一下..."
            hide-details
            :rows="inputRow"
            :disabled="isLoading"
            @keydown="handleKeydown"
            @focus="inputRow = 2"
            @blur="inputRow = 1"
          />

          <v-btn
            size="42"
            class="mb-1"
            color="primary"
            variant="elevated"
            icon
            :loading="isLoading"
            :disabled="isLoading || !userMessage.trim()"
            @click="sendMessage"
          >
            <v-icon size="20">mdi-send</v-icon>
          </v-btn>
        </v-sheet>
      </v-card>
    </transition>
  </teleport>
</template>

<style scoped lang="scss">
.dialog-bottom {
  z-index: 999;
  position: fixed;
  bottom: 10px;
  right: 0px;
}

.user-message {
  display: flex;
  align-content: center;
  justify-content: end;
  flex-direction: row-reverse;
}

.assistant-message {
  display: flex;
  align-content: center;
  justify-content: start;
  flex-direction: row;
}

// 还原作者用的"gradient gray"风格用户气泡
.gradient-gray {
  background: linear-gradient(135deg, #4a5568 0%, #2d3748 100%) !important;
  max-width: 75%;
}

.ai-card {
  max-width: 80%;
  background: rgba(255, 255, 255, 0.95) !important;
}

.text-pre-wrap {
  white-space: pre-wrap;
}

// ★ 关键：固定高度 + 原生滚动条（不依赖 perfect-scrollbar）
.message-container {
  height: 300px;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 8px 12px;
  scrollbar-width: thin;          // Firefox
  scrollbar-color: rgba(0, 0, 0, 0.25) transparent;

  // Chromium/WebKit
  &::-webkit-scrollbar {
    width: 8px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  &::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.2);
    border-radius: 4px;
    &:hover {
      background: rgba(0, 0, 0, 0.35);
    }
  }
}

.no-message-container {
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  flex-direction: column;
}

.font-1 {
  font-size: 13px !important;
}

.markdown-body :deep(p) {
  margin: 0 0 0.5em;
  &:last-child {
    margin-bottom: 0;
  }
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
