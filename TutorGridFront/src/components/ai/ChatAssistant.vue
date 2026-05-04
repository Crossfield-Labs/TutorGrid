<!--
  ChatAssistant: right drawer version for feat/frontend-b-improvements.
  It keeps this branch's drawer UI while using the persistent chat stores.
-->
<template>
  <v-btn
    v-if="!hideActivator"
    class="chat-fab"
    :class="{ 'fab-active': drawer }"
    size="50"
    color="primary"
    rounded="lg"
    elevation="8"
    @click="drawer = !drawer"
  >
    <v-icon size="28">
      {{ drawer ? "mdi-close" : "mdi-chat-outline" }}
    </v-icon>
    <v-tooltip activator="parent" location="left" text="智格生境 · AI 对话" />
  </v-btn>

  <v-navigation-drawer
    v-model="drawer"
    location="right"
    temporary
    :width="xs ? 360 : 420"
    class="chat-drawer"
    :touchless="false"
  >
    <div class="chat-drawer-inner d-flex flex-column fill-height">
      <div class="chat-header pa-3">
        <div class="d-flex align-center">
          <v-avatar size="36" class="mr-2">
            <v-img :src="avatarAssistant" alt="AI" />
          </v-avatar>
          <div class="d-flex flex-column flex-fill">
            <span class="text-body-2 font-weight-bold">智格生境 · AI 对话</span>
            <span class="text-caption text-medium-emphasis">{{ sessionLabel }}</span>
          </div>
          <v-tooltip location="bottom" text="新建会话">
            <template #activator="{ props: tipProps }">
              <v-btn
                v-bind="tipProps"
                icon="mdi-plus"
                variant="text"
                size="small"
                @click.stop="newSession"
              />
            </template>
          </v-tooltip>
        </div>

        <div v-if="currentDocId" class="mt-2 d-flex align-center">
          <v-chip-group
            :model-value="sessionId"
            mandatory
            selected-class="text-primary"
            @update:model-value="(value: any) => value && selectSession(value)"
          >
            <v-chip
              v-for="session in sessions"
              :key="session.id"
              :value="session.id"
              size="x-small"
              variant="outlined"
              prepend-icon="mdi-chat-outline"
            >
              {{ session.title }}
            </v-chip>
          </v-chip-group>
        </div>
      </div>
      <v-divider />

      <div class="chat-messages flex-fill">
        <div v-if="messages.length" ref="msgContainer" class="message-list pa-2">
          <template v-for="message in messages" :key="message.id">
            <div v-if="message.role === 'user'" class="msg-row user-row mb-2">
              <v-card class="msg-bubble user-bubble" theme="dark">
                <v-card-text class="pa-2">
                  <div
                    v-if="message.metadata?.origin === 'document' || message.metadata?.command"
                    class="text-caption opacity-70 mb-1 d-flex align-center"
                  >
                    <v-icon
                      size="11"
                      :icon="message.metadata?.origin === 'document' ? 'mdi-file-document-outline' : 'mdi-comment-outline'"
                      class="mr-1"
                    />
                    {{ message.metadata?.origin === "document" ? "文档引用" : "Chat" }}
                    <span v-if="message.metadata?.command" class="ml-1">
                      · {{ message.metadata.command }}
                    </span>
                  </div>
                  <b>{{ message.content }}</b>
                </v-card-text>
              </v-card>
              <v-avatar size="28" class="ml-1">
                <v-img :src="avatarUser" alt="user" />
              </v-avatar>
            </div>

            <div v-else class="msg-row ai-row mb-2">
              <v-avatar size="28" class="mr-1">
                <v-img :src="avatarAssistant" alt="AI" />
              </v-avatar>
              <v-card class="msg-bubble ai-bubble flex-fill">
                <v-card-text class="pa-2">
                  <div v-if="message.metadata?.toolsUsed?.length" class="mb-1">
                    <v-chip
                      v-for="tool in message.metadata.toolsUsed"
                      :key="tool"
                      size="x-small"
                      variant="tonal"
                      :color="tool.includes('rag') ? 'success' : 'info'"
                      class="mr-1 mb-1"
                    >
                      <v-icon
                        :icon="tool.includes('rag') ? 'mdi-bookshelf' : 'mdi-web'"
                        size="11"
                        class="mr-1"
                      />
                      {{ tool }}
                    </v-chip>
                  </div>

                  <div v-if="message.content" class="markdown-body" v-html="renderAi(message.content)" />

                  <div v-else-if="message.streaming" class="d-flex align-center text-medium-emphasis">
                    <v-progress-circular indeterminate size="14" width="2" color="primary" class="mr-2" />
                    AI 正在思考...
                  </div>

                  <div
                    v-if="!message.streaming && message.content && editorBus.hasActiveEditor.value"
                    class="d-flex justify-end mt-2"
                  >
                    <v-btn
                      size="x-small"
                      variant="text"
                      prepend-icon="mdi-pin-outline"
                      @click="insertToDocument(message.content, message.id)"
                    >
                      插入到文档
                    </v-btn>
                  </div>
                </v-card-text>
              </v-card>
            </div>
          </template>
        </div>

        <div v-else class="empty-state d-flex flex-column align-center justify-center fill-height text-grey">
          <v-icon icon="mdi-message-text-outline" size="48" class="mb-3" />
          <div class="text-h6 text-medium-emphasis">开始对话</div>
          <div class="text-caption text-disabled mt-1 text-center px-4">
            输入问题，AI 会从知识库 / 联网检索为你解答
          </div>
          <div class="text-caption text-disabled mt-3">{{ sessionLabel }}</div>
        </div>
      </div>
      <v-divider />

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
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useDisplay } from "vuetify";
import { useSnackbarStore } from "@/stores/snackbarStore";
import { useChatMessageStore } from "@/stores/chatMessageStore";
import { useChatSessionListStore } from "@/stores/chatSessionListStore";
import { useChatSessionStore } from "@/stores/chatSessionStore";
import { useDocumentEditorBus } from "@/composables/useDocumentEditorBus";
import { streamChat } from "@/lib/chat-sse";
import { renderMarkdown, postProcessLinks } from "@/lib/markdown";
import { scrollToBottom } from "@/utils/common";
import avatarAssistant from "@/assets/images/avatars/avatar_assistant.jpg";
import avatarUser from "@/assets/images/avatars/avatar_user.jpg";

const props = withDefaults(
  defineProps<{
    hideActivator?: boolean;
    openSignal?: number;
  }>(),
  {
    hideActivator: false,
    openSignal: 0,
  }
);

const snackbarStore = useSnackbarStore();
const chatMsgStore = useChatMessageStore();
const sessionListStore = useChatSessionListStore();
const chatSession = useChatSessionStore();
const editorBus = useDocumentEditorBus();
const { xs } = useDisplay();

const drawer = ref(false);
const userMessage = ref("");
const isLoading = ref(false);
const msgContainer = ref<HTMLElement | null>(null);

const currentDocId = computed(() => chatSession.currentDocId);
const sessionId = computed(() => chatSession.currentSessionId);
const sessions = computed(() => currentDocId.value ? sessionListStore.sessionsOf(currentDocId.value) : []);
const messages = computed(() => chatMsgStore.messagesOf(sessionId.value));

const renderAi = (text: string) => postProcessLinks(renderMarkdown(text));

const sessionLabel = computed(() => {
  if (!currentDocId.value) return "全局会话";
  return sessions.value.find((session) => session.id === sessionId.value)?.title || "默认会话";
});

async function loadSessionsAndDefault() {
  if (!currentDocId.value) {
    return;
  }
  const defaultSession = await sessionListStore.ensureDefault(currentDocId.value);
  if (defaultSession) {
    chatSession.setSession(defaultSession.id, currentDocId.value);
    await chatMsgStore.fetchBySession(defaultSession.id);
  }
}

async function selectSession(nextSessionId: string) {
  chatSession.setSession(nextSessionId, currentDocId.value);
  await chatMsgStore.fetchBySession(nextSessionId);
}

async function newSession() {
  if (!currentDocId.value) {
    snackbarStore.showWarningMessage("无文档场景下不支持新建会话");
    return;
  }
  const created = await sessionListStore.create(currentDocId.value);
  if (created) {
    await selectSession(created.id);
    snackbarStore.showSuccessMessage(`已新建：${created.title}`);
  }
}

async function sendMessage() {
  const text = userMessage.value.trim();
  if (!text) return;
  if (!sessionId.value) {
    snackbarStore.showErrorMessage("当前没有活跃 session");
    return;
  }

  chatMsgStore.pushUserMessage(sessionId.value, text);
  const aiMsg = chatMsgStore.startAiPlaceholder(sessionId.value);

  userMessage.value = "";
  isLoading.value = true;

  try {
    await streamChat({
      payload: {
        session_id: sessionId.value,
        message: text,
        course_id: chatSession.courseId || undefined,
        tools: ["rag", "tavily"],
        context: currentDocId.value ? { doc_id: currentDocId.value } : undefined,
      },
      onEvent: (event) => {
        switch (event.type) {
          case "tool_call":
            chatMsgStore.addToolUsed(sessionId.value, aiMsg.id, event.tool);
            break;
          case "tool_result":
            if (event.citations?.length) {
              chatMsgStore.addCitations(sessionId.value, aiMsg.id, event.citations);
            }
            if (event.results?.length) {
              chatMsgStore.addSearchResults(sessionId.value, aiMsg.id, event.results);
            }
            break;
          case "delta":
            chatMsgStore.appendDelta(sessionId.value, aiMsg.id, event.content);
            break;
          case "done":
            chatMsgStore.finishAi(sessionId.value, aiMsg.id);
            break;
          case "error":
            chatMsgStore.failAi(sessionId.value, aiMsg.id, event.message);
            snackbarStore.showErrorMessage(`AI 出错：${event.message}`);
            break;
        }
      },
    });
  } catch (error) {
    chatMsgStore.failAi(sessionId.value, aiMsg.id, (error as Error).message || "网络错误");
    snackbarStore.showErrorMessage(`Chat SSE 失败：${(error as Error).message}`);
  } finally {
    chatMsgStore.finishAi(sessionId.value, aiMsg.id);
    isLoading.value = false;
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === "Enter" && (e.altKey || e.shiftKey)) {
    e.preventDefault();
    userMessage.value += "\n";
  } else if (e.key === "Enter") {
    e.preventDefault();
    void sendMessage();
  }
};

function insertToDocument(messageContent: string, sourceMessageId: string) {
  if (!editorBus.hasActiveEditor.value) {
    snackbarStore.showWarningMessage("当前没有活跃的文档编辑器");
    return;
  }
  editorBus.insertAiBubble({ content: messageContent, sourceChatMessageId: sourceMessageId });
  snackbarStore.showSuccessMessage("已插入到文档");
}

function openDrawer() {
  drawer.value = true;
}

watch(
  () => props.openSignal,
  (value, oldValue) => {
    if (value !== oldValue && value > 0) openDrawer();
  }
);

watch(currentDocId, async (newId, oldId) => {
  if (newId !== oldId) await loadSessionsAndDefault();
});

watch(sessionId, async (newId) => {
  if (newId) await chatMsgStore.fetchBySession(newId);
});

watch(
  messages,
  () => {
    nextTick(() => scrollToBottom(msgContainer.value));
  },
  { deep: true }
);

onMounted(async () => {
  window.addEventListener("tutorgrid:open-chat", openDrawer);
  await loadSessionsAndDefault();
});

onBeforeUnmount(() => {
  window.removeEventListener("tutorgrid:open-chat", openDrawer);
});

defineExpose({ open: openDrawer, close: () => (drawer.value = false), toggle: () => (drawer.value = !drawer.value) });
</script>

<style scoped lang="scss">
.chat-fab {
  z-index: 998;
  position: fixed;
  bottom: 100px;
  right: 10px;
  transition: all 0.3s ease;

  &.fab-active {
    right: 430px;
  }
}

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

.chat-messages {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 0, 0, 0.2) transparent;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.2);
    border-radius: 3px;
  }
}

.empty-state {
  min-height: 300px;
}

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

.chat-input {
  flex-shrink: 0;
}

@media (max-width: 480px) {
  .chat-drawer {
    width: 100% !important;
  }

  .chat-fab.fab-active {
    right: 10px;
  }
}

.markdown-body :deep(p) {
  margin: 0 0 0.5em;
  font-size: 13px;

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
