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
        <!-- 主笔记区（左 6 栏，文档独立滚动）-->
        <v-col cols="12" md="6" class="pe-md-3 d-flex flex-column editor-col">
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
            :session-id="sessionId"
            class="flex-fill"
            @ready="onEditorReady"
            @ai-command="onAiCommand"
            @task-command="onTaskCommand"
          />
        </v-col>

        <!-- 磁贴区（右 6 栏 · F08 CSS Grid）-->
        <v-col cols="12" md="6" class="ps-md-3 tiles-col">
          <TileGrid
            :agent="activeAgent"
            :card="selectedCard"
            :task="activeTask"
            :task-starting="taskStore.starting"
            :auto-citations="autoCitations"
            :auto-artifacts="autoArtifacts"
            :initial-grid-cols="tileGridCols"
            :initial-tiles="tileGridTiles"
            @clear-card="selectedCard = null"
            @start-task="startTask"
            @resume-task="resumeTask"
            @interrupt-task="interruptTask"
            @update:tiles="onTileGridUpdate"
            @update:grid-cols="onGridColsUpdate"
          />
        </v-col>
      </v-row>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { Editor } from "@tiptap/vue-3";
import DocumentEditor from "./components/DocumentEditor.vue";
import TileGrid from "./components/TileGrid.vue";
import type { GridTile } from "./components/TileGrid.vue";
import { useWorkspaceStore } from "@/stores/workspaceStore";
import { useSnackbarStore } from "@/stores/snackbarStore";
import { useChatSessionStore, makeSessionId } from "@/stores/chatSessionStore";
import { useOrchestratorTaskStore } from "@/stores/orchestratorTaskStore";
import { useMessageStore } from "@/stores/messageStore";
import { useChatMessageStore } from "@/stores/chatMessageStore";
import type { ChatCitation } from "@/lib/chat-sse";

const route = useRoute();
const router = useRouter();
const workspaceStore = useWorkspaceStore();
const snackbarStore = useSnackbarStore();
const chatSession = useChatSessionStore();
const taskStore = useOrchestratorTaskStore();
const messageStore = useMessageStore();
const chatMessageStore = useChatMessageStore();

const tileId = computed(() => route.params.id as string);
const tile = computed(() => workspaceStore.findTile(tileId.value));

const title = ref("");
const content = ref("");
const loading = ref(true);
const saveStatus = ref<"idle" | "saving" | "saved" | "error">("idle");
const editorReady = ref(false);
const sessionId = ref("");

let saveTimer: ReturnType<typeof setTimeout> | null = null;

const selectedCard = ref<{
  title?: string;
  icon?: string;
  detail?: string;
} | null>(null);
const activeTask = computed(() => taskStore.activeTaskForDoc(tileId.value));
const autoArtifacts = computed(() => activeTask.value?.artifacts ?? []);
const activeAgent = computed(() => {
  if (!activeTask.value) return null;
  if (!["running", "awaiting_user"].includes(activeTask.value.status)) return null;
  return {
    title: activeTask.value.title || "编排任务",
    phase: activeTask.value.phase,
    worker: activeTask.value.awaitingUser
      ? "等待输入"
      : activeTask.value.steps[activeTask.value.currentStepIndex - 1]?.name || "",
    progress: Math.min(
      1,
      Math.max(0.05, activeTask.value.currentStepIndex / Math.max(1, activeTask.value.stepTotal)),
    ),
  };
});

const citationKey = (citation: ChatCitation) =>
  `${citation.source || citation.fileName || citation.fileId || ""}|${citation.page || ""}|${citation.chunk || citation.content || ""}`;

const autoCitations = computed<ChatCitation[]>(() => {
  const currentSession = sessionId.value;
  if (!currentSession) return [];
  const recentMessages = [
    ...messageStore.getSessionMessages(currentSession),
    ...chatMessageStore.messagesOf(currentSession),
  ].slice(-12);
  const seen = new Set<string>();
  const citations: ChatCitation[] = [];

  for (const message of recentMessages) {
    const metadata = message.metadata;
    for (const citation of metadata?.citations ?? []) {
      const key = citationKey(citation);
      if (seen.has(key)) continue;
      seen.add(key);
      citations.push(citation);
    }
    for (const result of metadata?.searchResults ?? []) {
      const citation: ChatCitation = {
        source: result.title || result.url || "联网检索结果",
        chunk: result.content || result.url || "",
        score: result.score,
      };
      const key = citationKey(citation);
      if (seen.has(key)) continue;
      seen.add(key);
      citations.push(citation);
    }
  }

  return citations.slice(-6);
});

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

  // F07：每个文档绑定一个 session id；从 metadata 读取，没有就新建并持久化
  const existing = tile.value.metadata?.sessionId;
  if (existing) {
    sessionId.value = existing;
  } else {
    sessionId.value = makeSessionId();
    await workspaceStore.setTileMetadata(tile.value.id, {
      sessionId: sessionId.value,
    });
  }
  // 把当前 session 注入全局 store，让 Toolbox 里的 ChatAssistant 能拿到
  chatSession.setSession(sessionId.value, tileId.value);

  // F08: 读取磁贴布局（从 metadata 恢复）
  const meta = tile.value.metadata || {};
  const rawTiles = meta.tileGrid;
  if (typeof rawTiles === "string" && rawTiles.trim()) {
    try {
      tileGridTiles.value = JSON.parse(rawTiles);
    } catch {
      // 解析失败则使用默认布局（组件内部 fallback）
    }
  }
  const rawCols = meta.tileGridCols;
  if (typeof rawCols === "string") {
    tileGridCols.value = parseInt(rawCols, 10) || 3;
  }

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
  // 离开文档时把全局 session 重置，让 Toolbox 回到 GLOBAL session
  chatSession.resetToGlobal();
});

// ─── F08: 磁贴 Grid 持久化 ───────────────────────────
const tileGridCols = ref(3);
const tileGridTiles = ref<GridTile[]>([]);

const onTileGridUpdate = async (tiles: GridTile[]) => {
  tileGridTiles.value = tiles;
  if (!tile.value) return;
  await workspaceStore.setTileMetadata(tile.value.id, {
    ...(tile.value.metadata || {}),
    tileGrid: JSON.stringify(tiles),
  });
};

const onGridColsUpdate = async (cols: number) => {
  tileGridCols.value = cols;
  if (!tile.value) return;
  await workspaceStore.setTileMetadata(tile.value.id, {
    ...(tile.value.metadata || {}),
    tileGridCols: String(cols),
  });
};

// AI 命令的实际处理在 DocumentEditor 内部完成，这里只接住事件用于（未来）日志/埋点
const onAiCommand = (_command: string, _payload?: unknown) => {
  // no-op
};

// F12: /task slash 命令 → 创建编排任务
const onTaskCommand = async (instruction: string) => {
  if (!instruction) {
    snackbarStore.showWarningMessage("请输入任务指令，例如 /task 帮我跑线性回归");
    return;
  }
  await startTask(instruction);
};

const startTask = async (instruction: string) => {
  try {
    await taskStore.createTask({
      docId: tileId.value,
      instruction,
    });
    snackbarStore.showSuccessMessage("编排任务已启动");
  } catch (error) {
    snackbarStore.showErrorMessage(`启动编排任务失败：${(error as Error).message}`);
  }
};

const resumeTask = async (content: string) => {
  if (!activeTask.value) return;
  try {
    await taskStore.resumeTask(activeTask.value.taskId, content);
    snackbarStore.showSuccessMessage("已提交补充输入");
  } catch (error) {
    snackbarStore.showErrorMessage(`继续执行失败：${(error as Error).message}`);
  }
};

const interruptTask = async () => {
  if (!activeTask.value) return;
  try {
    await taskStore.interruptTask(activeTask.value.taskId);
    snackbarStore.showSuccessMessage("已发送中断请求");
  } catch (error) {
    snackbarStore.showErrorMessage(`中断任务失败：${(error as Error).message}`);
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

.tiles-col {
  height: min(76vh, 760px);
  min-height: 540px;
  padding-top: 4px;
  padding-bottom: 20px;
  overflow: hidden;
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
  .tiles-col {
    height: auto;
    min-height: 0;
  }

  .tiles-col {
    padding-top: 16px;
    padding-bottom: 0;
    overflow: visible;
  }
}
</style>
