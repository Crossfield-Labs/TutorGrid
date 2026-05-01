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
            class="flex-fill"
            @ready="onEditorReady"
            @ai-command="onAiCommand"
          />
        </v-col>

        <!-- 磁贴区（右 6 栏 · F06 占位骨架）-->
        <v-col cols="12" md="6" class="ps-md-3 tiles-col">
          <TileGrid
            :agent="activeAgent"
            :card="selectedCard"
            @dismiss-agent="activeAgent = null"
            @clear-card="selectedCard = null"
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
import { useWorkspaceStore } from "@/stores/workspaceStore";
import { useSnackbarStore } from "@/stores/snackbarStore";

const route = useRoute();
const router = useRouter();
const workspaceStore = useWorkspaceStore();
const snackbarStore = useSnackbarStore();

const tileId = computed(() => route.params.id as string);
const tile = computed(() => workspaceStore.findTile(tileId.value));

const title = ref("");
const content = ref("");
const loading = ref(true);
const saveStatus = ref<"idle" | "saving" | "saved" | "error">("idle");
const editorReady = ref(false);

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

// [TODO F07] AI 命令处理 —— F07 重新接入 AiBubbleNode 时实现
const onAiCommand = (command: string, _payload?: unknown) => {
  snackbarStore.showInfoMessage(`[F07 待接入] 命令 ${command}`);
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
