<!--
* @Component: ChatAssistant
* @Description: AI 对话浮窗（Step 2 持久化版）
*
* 数据源：chatSessionListStore + chatMessageStore（替代旧 messageStore）
* 新功能：顶部 session tabs、新建/切换会话、AI 消息"📌 插入到文档"按钮
-->
<script setup lang="ts">
import { computed, nextTick, ref, watch, onMounted } from "vue";
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

const userMessage = ref("");
const isLoading = ref(false);
const inputRow = ref(1);
const dialog = ref(false);

watch(
  () => props.openSignal,
  (value, oldValue) => {
    if (value !== oldValue && value > 0) {
      dialog.value = true;
    }
  }
);

const currentDocId = computed(() => chatSession.currentDocId);
const sessionId = computed(() => chatSession.currentSessionId);

const sessions = computed(() =>
  currentDocId.value ? sessionListStore.sessionsOf(currentDocId.value) : []
);
const messages = computed(() => chatMsgStore.messagesOf(sessionId.value));

const renderAi = (text: string) => postProcessLinks(renderMarkdown(text));

const sessionLabel = computed(() => {
  if (!currentDocId.value) return "全局会话";
  const cur = sessions.value.find((s) => s.id === sessionId.value);
  return cur?.title || "默认会话";
});

// ---------------- 会话生命周期 ----------------

async function loadSessionsAndDefault() {
  if (!currentDocId.value) return;
  const def = await sessionListStore.ensureDefault(currentDocId.value);
  if (def) {
    chatSession.setSession(def.id, currentDocId.value);
    await chatMsgStore.fetchBySession(def.id);
  }
}

// 监听 docId 变化（切换 hyperdoc 时）
watch(currentDocId, async (newId, oldId) => {
  if (newId && newId !== oldId) await loadSessionsAndDefault();
});

// 监听 session 切换 → fetch 消息
watch(sessionId, async (newId) => {
  if (newId) await chatMsgStore.fetchBySession(newId);
});

onMounted(async () => {
  if (currentDocId.value) await loadSessionsAndDefault();
});

async function selectSession(sid: string) {
  chatSession.setSession(sid, currentDocId.value);
  await chatMsgStore.fetchBySession(sid);
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

// ---------------- 发送消息（SSE） ----------------

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
  } catch (e) {
    chatMsgStore.failAi(sessionId.value, aiMsg.id, (e as Error).message || "网络错误");
    snackbarStore.showErrorMessage(`Chat SSE 失败：${(e as Error).message}`);
  } finally {
    chatMsgStore.finishAi(sessionId.value, aiMsg.id);
    isLoading.value = false;
  }
}

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

// 跨视图同步 #8：把 AI 消息插入到当前文档（通过 editorBus）
function insertToDocument(messageContent: string, sourceMessageId: string) {
  if (!editorBus.hasActiveEditor.value) {
    snackbarStore.showWarningMessage("当前没有活跃的文档编辑器");
    return;
  }
  editorBus.insertAiBubble({
    content: messageContent,
    sourceChatMessageId: sourceMessageId,
  });
  snackbarStore.showSuccessMessage("已插入到文档");
}
</script>

<template>
  <v-btn v-if="!hideActivator" size="50" @click="dialog = !dialog">
    <v-icon size="30">mdi-chat-outline</v-icon>
    <v-tooltip activator="parent" location="left" text="AI 对话" />
  </v-btn>

  <teleport to="body">
    <transition name="slide-y">
      <v-card
        v-if="dialog"
        class="dialog-bottom d-flex flex-column"
        :width="xs ? '100%' : '600px'"
        height="600px"
      >
        <v-card-title class="pb-1">
          <span class="flex-fill d-inline-flex align-center">
            <v-avatar size="36" class="mr-2">
              <v-img :src="avatarAssistant" alt="AI" />
            </v-avatar>
            <div class="d-flex flex-column">
              <span class="text-body-1">智格生境 · AI 对话</span>
              <span class="text-caption text-medium-emphasis">
                {{ sessionLabel }}
              </span>
            </div>
          </span>

          <v-spacer />
          <v-btn icon variant="text" size="small" @click.stop="dialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>

        <!-- Session Tabs -->
        <div v-if="currentDocId" class="px-2 pb-1 d-flex align-center">
          <v-chip-group
            :model-value="sessionId"
            mandatory
            selected-class="text-primary"
            @update:model-value="(v: any) => v && selectSession(v)"
          >
            <v-chip
              v-for="s in sessions"
              :key="s.id"
              :value="s.id"
              size="small"
              variant="outlined"
              prepend-icon="mdi-chat-outline"
            >
              {{ s.title }}
            </v-chip>
          </v-chip-group>
          <v-spacer />
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

        <v-divider />

        <v-card-text class="pa-0 flex-fill" style="overflow: hidden">
          <div v-if="messages.length > 0" class="message-container">
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
                            ? "文档引用"
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
                            :icon="t.includes('rag') ? 'mdi-bookshelf' : 'mdi-web'"
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
                        />
                        AI 正在思考…
                      </div>

                      <!-- 跨视图同步：插入到文档 -->
                      <div
                        v-if="
                          !message.streaming &&
                          message.content &&
                          editorBus.hasActiveEditor.value
                        "
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
            <div class="text-caption text-disabled mt-3">{{ sessionLabel }}</div>
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

.message-container {
  height: 100%;
  overflow-y: auto;
  padding-bottom: 8px;
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

.gradient-gray {
  background: linear-gradient(135deg, #4a5568 0%, #2d3748 100%) !important;
  max-width: 75%;
}

.ai-card {
  max-width: 80%;
}

.no-message-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 24px;
  text-align: center;
}
</style>
