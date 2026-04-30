<template>
  <!-- 浮动按钮 -->
  <v-btn
    v-show="!open"
    icon="mdi-robot-outline"
    color="primary"
    size="large"
    elevation="6"
    class="chat-fab"
    @click="open = true"
  />

  <!-- 抽屉 -->
  <v-navigation-drawer
    v-model="open"
    location="right"
    temporary
    width="400"
    class="chat-drawer"
  >
    <div class="d-flex flex-column" style="height: 100%">
      <div class="d-flex align-center pa-3 chat-header">
        <v-icon icon="mdi-robot-outline" color="primary" class="mr-2" />
        <span class="text-subtitle-1 font-weight-bold flex-fill">AI 同桌</span>
        <v-chip
          size="x-small"
          variant="tonal"
          :color="sessionStatusColor"
          class="mr-2"
        >
          <v-icon :icon="sessionStatusIcon" size="12" class="mr-1" />
          {{ sessionStatusText }}
        </v-chip>
        <v-btn
          icon="mdi-close"
          variant="text"
          size="small"
          @click="open = false"
        />
      </div>

      <v-divider />

      <div class="flex-fill chat-body pa-3">
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="d-flex mb-3"
          :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
        >
          <v-avatar
            v-if="msg.role === 'ai'"
            size="32"
            color="primary"
            class="mr-2"
          >
            <v-icon icon="mdi-robot-outline" size="18" color="white" />
          </v-avatar>
          <v-card
            :color="msg.role === 'user' ? 'primary' : undefined"
            :variant="msg.role === 'user' ? 'flat' : 'flat'"
            class="msg-bubble pa-3"
            :class="msg.role"
          >
            <div class="text-body-2 chat-text">{{ msg.text }}</div>
            <div
              v-if="msg.streaming"
              class="text-caption mt-1 chat-stream-hint"
            >
              <v-icon icon="mdi-loading" size="12" class="mr-1 chat-loading" />
              正在输出…
            </div>
          </v-card>
          <v-avatar
            v-if="msg.role === 'user'"
            size="32"
            color="grey-lighten-2"
            class="ml-2"
          >
            <v-icon icon="mdi-account-outline" size="18" />
          </v-avatar>
        </div>

        <div
          v-if="messages.length === 0"
          class="text-center text-caption text-medium-emphasis py-8"
        >
          <v-icon icon="mdi-robot-confused-outline" size="32" class="mb-2" />
          <div>开始和 AI 同桌聊聊</div>
          <div class="mt-1">它能看到你正在写的文档</div>
        </div>
      </div>

      <v-divider />

      <div class="pa-3 chat-input-area">
        <v-textarea
          v-model="input"
          variant="outlined"
          density="compact"
          rows="2"
          auto-grow
          hide-details
          :placeholder="sending ? '正在等待 AI 响应…' : '问点什么...'"
          :disabled="sending"
          @keydown.enter.prevent.exact="onSend"
        >
          <template #append-inner>
            <v-btn
              icon="mdi-send"
              variant="text"
              size="small"
              color="primary"
              :disabled="!input.trim() || sending"
              @click="onSend"
            />
          </template>
        </v-textarea>
      </div>
    </div>
  </v-navigation-drawer>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useOrchestratorStore } from "@/stores/orchestratorStore";
import { useWorkspaceStore } from "@/stores/workspaceStore";
import { useSnackbarStore } from "@/stores/snackbarStore";

interface ChatMessage {
  id: string;
  role: "user" | "ai";
  text: string;
  ts: number;
  streaming?: boolean;
  messageId?: string;
}

const props = defineProps<{ tileId?: string }>();

const orchestratorStore = useOrchestratorStore();
const workspaceStore = useWorkspaceStore();
const snackbarStore = useSnackbarStore();

const open = ref(false);
const input = ref("");
const messages = ref<ChatMessage[]>([]);
const sending = ref(false);

let unsubSession: (() => void) | null = null;
let subscribedSessionId = "";

const tileSessionId = computed<string>(() => {
  if (!props.tileId) return "";
  const tile = workspaceStore.findTile(props.tileId);
  return tile?.metadata?.sessionId || "";
});

const sessionStatusText = computed(() => {
  if (!orchestratorStore.isLive) return "离线（mock）";
  if (tileSessionId.value) return "共享会话";
  return "未开会话";
});

const sessionStatusColor = computed(() => {
  if (!orchestratorStore.isLive) return "grey";
  if (tileSessionId.value) return "primary";
  return "warning";
});

const sessionStatusIcon = computed(() => {
  if (!orchestratorStore.isLive) return "mdi-cloud-off-outline";
  if (tileSessionId.value) return "mdi-link-variant";
  return "mdi-circle-outline";
});

const subscribeIfNeeded = (sid: string) => {
  if (!sid || sid === subscribedSessionId) return;
  if (unsubSession) {
    unsubSession();
    unsubSession = null;
  }
  subscribedSessionId = sid;
  unsubSession = orchestratorStore.subscribeSession(sid, (event, payload) => {
    handleSessionEvent(event, payload);
  });
};

const handleSessionEvent = (event: string, payload: any) => {
  if (event === "orchestrator.session.message.started") {
    const last = messages.value[messages.value.length - 1];
    if (last && last.role === "ai" && !last.messageId) {
      last.messageId = payload.messageId;
      last.streaming = true;
      return;
    }
    messages.value.push({
      id: `ai_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      role: "ai",
      text: "",
      ts: Date.now(),
      streaming: true,
      messageId: payload.messageId,
    });
    return;
  }
  if (event === "orchestrator.session.message.delta") {
    const m = messages.value.find((x) => x.messageId === payload.messageId);
    if (m) {
      m.text += payload.delta || "";
    }
    return;
  }
  if (event === "orchestrator.session.message.completed") {
    const m = messages.value.find((x) => x.messageId === payload.messageId);
    if (m) {
      m.text = payload.content || m.text;
      m.streaming = false;
    }
    stopSending();
    return;
  }
  if (event === "orchestrator.session.failed") {
    const m = messages.value[messages.value.length - 1];
    if (m && m.role === "ai" && m.streaming) {
      m.streaming = false;
      m.text = m.text || `（任务失败：${payload?.message || "未知错误"}）`;
    }
    stopSending();
    return;
  }
};

watch(
  tileSessionId,
  (sid) => {
    if (sid) subscribeIfNeeded(sid);
  },
  { immediate: true }
);

const persistSessionId = async (sessionId: string) => {
  if (!props.tileId || !sessionId) return;
  await workspaceStore.setTileMetadata(props.tileId, { sessionId });
};

let sendingTimer: ReturnType<typeof setTimeout> | null = null;
const SENDING_TIMEOUT_MS = 90_000;

const startSending = () => {
  sending.value = true;
  if (sendingTimer) clearTimeout(sendingTimer);
  sendingTimer = setTimeout(() => {
    sending.value = false;
    sendingTimer = null;
    const m = messages.value[messages.value.length - 1];
    if (m && m.role === "ai" && m.streaming) {
      m.streaming = false;
      m.text = m.text || "（90 秒未收到回复，已解锁输入。后端 LLM 可能挂了或太慢）";
    }
  }, SENDING_TIMEOUT_MS);
};

const stopSending = () => {
  sending.value = false;
  if (sendingTimer) {
    clearTimeout(sendingTimer);
    sendingTimer = null;
  }
};

const onSend = async () => {
  const text = input.value.trim();
  if (!text || sending.value) return;
  messages.value.push({
    id: `u_${Date.now()}`,
    role: "user",
    text,
    ts: Date.now(),
  });
  input.value = "";

  if (!orchestratorStore.isLive) {
    setTimeout(() => {
      messages.value.push({
        id: `ai_${Date.now()}`,
        role: "ai",
        text: "（mock）后端 WebSocket 未连接，这里只是占位回复。",
        ts: Date.now(),
      });
    }, 600);
    return;
  }

  // pending AI bubble shows "正在思考..." immediately so user sees something
  messages.value.push({
    id: `ai_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    role: "ai",
    text: "",
    ts: Date.now(),
    streaming: true,
  });

  startSending();
  try {
    const existing = tileSessionId.value;
    if (!existing) {
      const { sessionId } = await orchestratorStore.runTipTapCommand({
        command: "ask",
        selectionText: text,
        documentText: "",
        workspace: workspaceStore.root || undefined,
      });
      if (sessionId) {
        await persistSessionId(sessionId);
        subscribeIfNeeded(sessionId);
      }
    } else {
      subscribeIfNeeded(existing);
      await orchestratorStore.sessionInput({
        sessionId: existing,
        intent: "instruction",
        text,
      });
    }
  } catch (e) {
    stopSending();
    const m = messages.value[messages.value.length - 1];
    if (m && m.role === "ai") {
      m.streaming = false;
      m.text = `（发送失败：${(e as Error).message}）`;
    }
    snackbarStore.showErrorMessage(`发送失败：${(e as Error).message}`);
  }
};

onMounted(() => {
  if (
    orchestratorStore.status === "idle" ||
    orchestratorStore.status === "disconnected"
  ) {
    orchestratorStore.connect().catch(() => {
      /* fall back to mock */
    });
  }
});

onBeforeUnmount(() => {
  if (unsubSession) {
    unsubSession();
    unsubSession = null;
  }
  if (sendingTimer) {
    clearTimeout(sendingTimer);
    sendingTimer = null;
  }
});

defineExpose({
  open: (initialText?: string) => {
    open.value = true;
    if (initialText) input.value = initialText;
  },
});
</script>

<style scoped lang="scss">
.chat-fab {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 1006;
}

.chat-drawer {
  z-index: 2000;
}

.chat-header {
  background: rgba(var(--v-theme-primary), 0.04);
}

.chat-body {
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.015);
}

.msg-bubble {
  max-width: 80%;
  border-radius: 12px;

  &.user {
    border-bottom-right-radius: 4px;
  }

  &.ai {
    border-bottom-left-radius: 4px;
    background: #ffffff !important;
    border: 1px solid rgba(15, 23, 42, 0.1);
    color: rgba(15, 23, 42, 0.9);
  }
}

.chat-text {
  white-space: pre-wrap;
  word-break: break-word;
  color: inherit;
}

.msg-bubble.user .chat-text {
  color: #ffffff;
}

.msg-bubble.ai .chat-text {
  color: rgba(15, 23, 42, 0.92);
}

.chat-stream-hint {
  color: rgba(15, 23, 42, 0.55);
}

.msg-bubble.user .chat-stream-hint {
  color: rgba(255, 255, 255, 0.85);
}

.chat-input-area {
  background: rgb(var(--v-theme-surface));
}

.chat-loading {
  animation: chat-spin 1.2s linear infinite;
}

@keyframes chat-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
