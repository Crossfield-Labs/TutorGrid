<!--
* @Component: ChatAssistant
* @Description: AI 对话浮窗 (来自旧项目，重写为占位版)
*
* ⚠️ F07 / F11 待替换的部分用 [TODO F07] 标记：
*   - sendMessage / createCompletion 改为调 /api/chat/stream SSE
*   - messages 改为消费统一消息 store (messageStore)
*   - markdown 渲染：暂时用纯文本，后续接 marked / md-editor-v3 二选一
-->
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useDisplay } from "vuetify";
import { useSnackbarStore } from "@/stores/snackbarStore";
import { scrollToBottom } from "@/utils/common";
import avatarAssistant from "@/assets/images/avatars/avatar_assistant.jpg";
import avatarUser from "@/assets/images/avatars/avatar_user.jpg";

const snackbarStore = useSnackbarStore();
const { xs } = useDisplay();

interface Message {
  content: string;
  role: "user" | "assistant" | "system";
}

// [TODO F11] 改成消费 messageStore.getChatMessages(sessionId)
const messages = ref<Message[]>([]);

const userMessage = ref("");
const isLoading = ref(false);
const inputRow = ref(1);
const dialog = ref(false);

// [TODO F07] 整段替换为 fetch('/api/chat/stream') + ReadableStream 消费 SSE
//   - on 'start' → push assistant 占位消息
//   - on 'delta' → 追加 content 到最后一条 assistant 消息
//   - on 'tool_call' / 'tool_result' → 推到右侧 TileGrid 的 CitationTile
//   - on 'done' → 标记完成
//   - on 'error' → snackbar 报错
const sendMessage = async () => {
  if (!userMessage.value.trim()) return;
  messages.value.push({ content: userMessage.value, role: "user" });
  const userText = userMessage.value;
  userMessage.value = "";
  isLoading.value = true;

  // 占位：模拟 800ms 后回一个固定回复，让 UI 流程能跑通
  await new Promise((r) => setTimeout(r, 800));
  messages.value.push({
    role: "assistant",
    content: `[占位回复] 你说的是「${userText}」。F07 接入后会走 /api/chat/stream，由 DeepSeek + RAG/Tavily 真实回答。`,
  });
  isLoading.value = false;
};

watch(
  messages,
  () => {
    scrollToBottom(document.querySelector(".message-container"));
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
  // [TODO F16] 打开"系统配置"对话框（API Key / Model）
  snackbarStore.showInfoMessage("系统配置功能将在 F16 安装向导中实现");
};

// 占位 user 信息（[TODO F11] 接 profileStore 后替换）
const user = computed(() => ({
  avatarUrl: avatarUser,
  name: "你",
}));
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
            智格生境 · AI 对话
          </span>

          <v-spacer />
          <v-btn icon variant="text" @click.stop="dialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-divider />

        <v-card-text class="overflow-scroll pa-0">
          <perfect-scrollbar
            v-if="messages.length > 0"
            class="message-container"
          >
            <template v-for="(message, idx) in messages" :key="idx">
              <div v-if="message.role === 'user'" class="pa-2 user-message">
                <v-avatar class="ml-2" rounded="sm" variant="elevated">
                  <v-img :src="user.avatarUrl" alt="user" />
                </v-avatar>
                <v-card class="user-bubble text-pre-wrap" theme="dark">
                  <v-card-text>
                    <b>{{ message.content }}</b>
                  </v-card-text>
                </v-card>
              </div>
              <div v-else class="pa-2 assistant-message">
                <v-avatar
                  class="d-none d-md-block mr-2"
                  rounded="sm"
                  variant="elevated"
                >
                  <v-img :src="avatarAssistant" alt="AI" />
                </v-avatar>
                <v-card>
                  <v-card-text class="text-body-2 message-content">
                    {{ message.content }}
                  </v-card-text>
                </v-card>
              </div>
            </template>
          </perfect-scrollbar>

          <div v-else class="no-message-container">
            <v-icon icon="mdi-message-text-outline" size="48" color="grey" />
            <h1 class="text-h6 text-medium-emphasis mt-3">开始对话</h1>
            <div class="text-caption text-disabled mt-1">
              输入问题，AI 会从知识库 / 联网检索为你解答
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

.user-bubble {
  background: linear-gradient(135deg, #4a5568 0%, #2d3748 100%);
  max-width: 75%;
}

.message-container {
  height: 360px;
  padding: 8px 4px;
}

.no-message-container {
  height: 360px;
  display: flex;
  justify-content: center;
  align-items: center;
  flex-direction: column;
}

.message-content {
  white-space: pre-wrap;
  word-break: break-word;
}

.text-pre-wrap {
  white-space: pre-wrap;
}
</style>
