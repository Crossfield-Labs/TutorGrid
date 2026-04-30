<template>
  <div class="hyperdoc-page d-flex flex-column">
    <!-- 顶栏 -->
    <div class="d-flex align-center px-3 py-2 hyperdoc-header flex-shrink-0">
      <v-btn
        prepend-icon="mdi-arrow-left"
        variant="text"
        @click="goBack"
      >
        返回工作区
      </v-btn>
      <v-text-field
        v-model="title"
        variant="plain"
        hide-details
        density="comfortable"
        placeholder="文档标题"
        class="title-input mx-3 flex-fill"
        @blur="saveTitle"
      />
      <v-tooltip
        location="bottom"
        :text="orchestratorStore.forceMock ? '当A' : 'B'"
      >
        <template #activator="{ props: tipProps }">
          <v-btn
            v-bind="tipProps"
            :prepend-icon="orchestratorStore.forceMock ? 'mdi-theater' : 'mdi-theater-outline'"
            variant="text"
            size="small"
            :color="orchestratorStore.forceMock ? 'warning' : 'grey-darken-1'"
            class="mr-2"
            @click="toggleDemoMode"
          >
            {{ orchestratorStore.forceMock ? 'A模式' : 'B模式' }}
          </v-btn>
        </template>
      </v-tooltip>

      <v-tooltip
        v-if="currentSessionId"
        location="bottom"
        text="清掉本文档绑定的旧 sessionId（适合演示前先按一下）"
      >
        <template #activator="{ props: tipProps }">
          <v-btn
            v-bind="tipProps"
            prepend-icon="mdi-restart"
            variant="text"
            size="small"
            color="warning"
            class="mr-2"
            @click="resetSession"
          >
            重置会话
          </v-btn>
        </template>
      </v-tooltip>
      <v-btn
        prepend-icon="mdi-export"
        variant="tonal"
        size="small"
        :disabled="!editorReady"
        @click="exportPdf"
      >
        导出 PDF
      </v-btn>
    </div>

    <!-- 主体（固定一屏，内部滚） -->
    <div class="hyperdoc-body flex-fill">
      <v-row no-gutters class="h-100">
        <!-- 主笔记区（左 9 栏，内部文档独立滚动）-->
        <v-col cols="12" md="9" class="pe-md-3 d-flex flex-column editor-col">
          <div
            v-if="loading"
            class="d-flex align-center justify-center flex-fill"
          >
            <v-progress-circular indeterminate color="primary" />
          </div>
          <v-card
            v-else-if="!tile"
            class="d-flex flex-column align-center justify-center flex-fill card-shadow"
            elevation="2"
            rounded="lg"
          >
            <v-icon icon="mdi-file-question-outline" size="48" color="grey" />
            <div class="text-grey mt-2">未找到文档</div>
          </v-card>
          <DocumentEditor
            v-else
            v-model="content"
            :save-status="saveStatus"
            :tile-id="tileId"
            class="flex-fill"
            @ready="onEditorReady"
            @ai-command="onAiCommand"
          />
        </v-col>

        <!-- 辅助区（右 3栏，比左栏更短）-->
        <v-col cols="12" md="3" class="ps-md-3 aside-col">
          <AsidePanel
            :active-agent="activeAgent"
            :selected-card="selectedCard"
            @dismiss-agent="activeAgent = null"
            @clear-card="selectedCard = null"
          />
        </v-col>
      </v-row>
    </div>

    <ChatFAB ref="chatRef" :tile-id="tileId" />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { Editor } from "@tiptap/vue-3";
import DocumentEditor from "./components/DocumentEditor.vue";
import AsidePanel from "./components/AsidePanel.vue";
import ChatFAB from "./components/ChatFAB.vue";
import { useWorkspaceStore } from "@/stores/workspaceStore";
import { useSnackbarStore } from "@/stores/snackbarStore";
import { useOrchestratorStore } from "@/stores/orchestratorStore";

const route = useRoute();
const router = useRouter();
const workspaceStore = useWorkspaceStore();
const snackbarStore = useSnackbarStore();
const orchestratorStore = useOrchestratorStore();

const toggleDemoMode = () => {
  const next = !orchestratorStore.forceMock;
  orchestratorStore.setForceMock(next);
  snackbarStore.showInfoMessage(
    next
      ? "已切到演示模式：所有 AI 命令走本地 mock 数据"
      : "已切回真实模式：使用后端 LLM"
  );
};

const tileId = computed(() => route.params.id as string);
const tile = computed(() => workspaceStore.findTile(tileId.value));

const title = ref("");
const content = ref("");
const loading = ref(true);
const saveStatus = ref<"idle" | "saving" | "saved" | "error">("idle");
const editorReady = ref(false);
const chatRef = ref<{ open: (text?: string) => void } | null>(null);

let saveTimer: ReturnType<typeof setTimeout> | null = null;

const activeAgent = ref<{
  title: string;
  phase: string;
  worker?: string;
  progress: number;
} | null>(null);
const selectedCard = ref<{
  title?: string;
  icon?: string;
  detail?: string;
} | null>(null);

const goBack = () => router.push("/board");

const saveTitle = async () => {
  if (!tile.value) return;
  if (title.value.trim() && title.value !== tile.value.title) {
    await workspaceStore.updateTile(tile.value.id, {
      title: title.value.trim(),
    });
  }
};

const onEditorReady = (_editor: Editor) => {
  editorReady.value = true;
};

watch(content, () => {
  if (loading.value) return;
  if (saveTimer) clearTimeout(saveTimer);
  saveStatus.value = "saving";
  saveTimer = setTimeout(async () => {
    if (!tile.value || tile.value.source?.kind !== "hyperdoc") return;
    try {
      await workspaceStore.writeText(tile.value.source.relPath, content.value);
      saveStatus.value = "saved";
    } catch (e) {
      console.error(e);
      saveStatus.value = "error";
      snackbarStore.showErrorMessage("保存失败");
    }
  }, 600);
});

const exportPdf = async () => {
  snackbarStore.showInfoMessage("PDF 导出功能将在 Phase 4 接入");
};

const currentSessionId = computed(
  () => tile.value?.metadata?.sessionId || ""
);

const resetSession = async () => {
  if (!tile.value) return;
  await workspaceStore.setTileMetadata(tile.value.id, { sessionId: undefined });
  snackbarStore.showSuccessMessage("已清除本文档的会话绑定");
};

watch(tile, (t) => {
  if (t) title.value = t.title;
});

onMounted(async () => {
  await workspaceStore.init();
  if (
    !tile.value ||
    tile.value.kind !== "hyperdoc" ||
    tile.value.source?.kind !== "hyperdoc"
  ) {
    loading.value = false;
    return;
  }
  title.value = tile.value.title;
  try {
    content.value = await workspaceStore.readText(tile.value.source.relPath);
  } catch (e) {
    console.error(e);
    snackbarStore.showErrorMessage("文档加载失败");
  } finally {
    loading.value = false;
  }
});

onBeforeUnmount(() => {
  if (saveTimer) clearTimeout(saveTimer);
});

const onAiCommand = (command: string, payload?: any) => {
  if (command === "send-to-chat") {
    chatRef.value?.open(payload?.selectionText || "");
  }
};
</script>

<style scoped lang="scss">
.hyperdoc-page {
  height: 100%;
  min-height: 0;
  max-height: 100%;
  padding: 14px 18px 24px;
  overflow: hidden;
}

.hyperdoc-header {
  margin-bottom: 14px;
}

.title-input :deep(input) {
  font-size: 1.4rem;
  font-weight: 600;
}

.hyperdoc-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

.editor-col {
  height: min(76vh, 760px);
  min-height: 540px;
}

.aside-col {
  height: min(68vh, 680px);
  min-height: 460px;
  padding-top: 10px;
  padding-bottom: 20px;
}

.h-100 {
  height: 100%;
}

@media (max-width: 959px) {
  .hyperdoc-page {
    height: auto;
    max-height: none;
    overflow: auto;
  }

  .hyperdoc-body {
    overflow: visible;
  }

  .editor-col,
  .aside-col {
    height: auto;
    min-height: 0;
  }

  .aside-col {
    padding-top: 16px;
    padding-bottom: 0;
  }
}
</style>
