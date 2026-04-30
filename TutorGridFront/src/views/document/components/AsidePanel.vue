<template>
  <v-card
    class="aside-panel d-flex flex-column card-shadow"
    elevation="0"
  >
    <v-tabs
      v-model="activeTab"
      color="primary"
      grow
      height="64"
      class="aside-tabs flex-shrink-0"
    >
      <v-tab value="files">
        <v-icon icon="mdi-folder-outline" size="20" class="mr-2" />
        工作区文件
        <v-chip
          v-if="fileTiles.length"
          size="x-small"
          variant="tonal"
          color="primary"
          class="ml-2"
        >
          {{ fileTiles.length }}
        </v-chip>
      </v-tab>
      <v-tab value="card">
        <v-icon icon="mdi-card-text-outline" size="20" class="mr-2" />
        节点详情
      </v-tab>
      <v-tab value="knowledge">
        <v-icon icon="mdi-bookshelf" size="20" class="mr-2" />
        知识库
        <v-chip
          v-if="knowledgeStore.files.length"
          size="x-small"
          variant="tonal"
          color="success"
          class="ml-2"
        >
          {{ knowledgeStore.files.length }}
        </v-chip>
      </v-tab>
    </v-tabs>

    <v-divider />

    <v-window v-model="activeTab" class="aside-window flex-fill">
      <!-- 文件列表 Tab -->
      <v-window-item value="files">
        <div class="aside-scroll">
          <v-list
            density="comfortable"
            lines="two"
            nav
            class="file-list px-2 py-1"
          >
            <v-list-item
              v-for="tile in fileTiles"
              :key="tile.id"
              :title="tile.title"
              :subtitle="subtitleFor(tile)"
              rounded="md"
              class="file-list-item"
            >
              <template #prepend>
                <v-icon
                  :icon="iconFor(tile)"
                  :color="colorFor(tile)"
                  size="22"
                />
              </template>
              <template #append>
                <v-tooltip location="top" text="加入默认知识库">
                  <template #activator="{ props: tipProps }">
                    <v-btn
                      v-bind="tipProps"
                      icon="mdi-database-plus-outline"
                      variant="text"
                      size="x-small"
                      color="success"
                      :loading="!!ingesting[tile.id]"
                      @click.stop="ingestTile(tile)"
                    />
                  </template>
                </v-tooltip>
                <v-tooltip location="top" text="查看节点">
                  <template #activator="{ props: tipProps }">
                    <v-btn
                      v-bind="tipProps"
                      icon="mdi-eye-outline"
                      variant="text"
                      size="x-small"
                      @click.stop="$emit('inspectFile', tile)"
                    />
                  </template>
                </v-tooltip>
              </template>
            </v-list-item>
          </v-list>

          <div
            v-if="fileTiles.length === 0"
            class="text-center text-caption text-medium-emphasis py-8 px-4"
          >
            <v-icon icon="mdi-folder-open-outline" size="32" class="mb-2" />
            <div>工作区暂无文件</div>
            <div class="mt-1">回到工作区拖入文件即可</div>
          </div>
        </div>
      </v-window-item>

      <!-- 知识库 Tab -->
      <v-window-item value="knowledge">
        <div class="aside-scroll px-3 py-3">
          <v-card
            variant="flat"
            rounded="md"
            class="aside-info-card pa-3 mb-3"
          >
            <div class="d-flex align-center mb-2">
              <v-icon
                icon="mdi-school-outline"
                size="18"
                color="success"
                class="mr-2"
              />
              <span class="text-subtitle-2 font-weight-bold flex-fill">
                {{ knowledgeStore.courseName || "MetaAgent 默认课程" }}
              </span>
              <v-btn
                icon="mdi-refresh"
                size="x-small"
                variant="text"
                :loading="knowledgeStore.loading"
                @click="ensureCourseAndRefresh"
              />
            </div>
            <div class="text-caption text-medium-emphasis">
              <span v-if="knowledgeStore.courseId">
                courseId: {{ knowledgeStore.courseId.slice(0, 12) }}…
              </span>
              <span v-else>未初始化（点右上刷新自动建库）</span>
            </div>
          </v-card>

          <div class="d-flex align-center mb-2">
            <v-icon icon="mdi-format-list-bulleted" size="14" class="mr-1" />
            <span class="text-caption font-weight-medium">已入库文件</span>
            <v-chip
              size="x-small"
              variant="tonal"
              color="success"
              class="ml-2"
            >
              {{ knowledgeStore.files.length }}
            </v-chip>
          </div>

          <v-list density="compact" class="ai-knowledge__list">
            <v-list-item
              v-for="file in knowledgeStore.files"
              :key="file.fileId"
              :title="file.fileName"
              :subtitle="fileSubtitle(file)"
              rounded="md"
              class="mb-1"
            >
              <template #prepend>
                <v-icon
                  :icon="iconForExt(file.fileExt)"
                  size="18"
                  :color="parseStatusColor(file.parseStatus)"
                />
              </template>
              <template #append>
                <v-chip
                  v-if="file.chunkCount && file.chunkCount > 0"
                  size="x-small"
                  variant="tonal"
                  color="success"
                >
                  {{ file.chunkCount }} chunks
                </v-chip>
                <v-tooltip
                  v-else-if="file.parseStatus && file.parseStatus !== 'success'"
                  :text="file.parseError || file.parseStatus"
                >
                  <template #activator="{ props: tipProps }">
                    <v-chip
                      v-bind="tipProps"
                      size="x-small"
                      variant="tonal"
                      :color="parseStatusColor(file.parseStatus)"
                    >
                      {{ parseStatusLabel(file.parseStatus) }}
                    </v-chip>
                  </template>
                </v-tooltip>
                <v-chip
                  v-else
                  size="x-small"
                  variant="tonal"
                  color="grey"
                >
                  已入库
                </v-chip>
              </template>
            </v-list-item>
          </v-list>

          <div
            v-if="knowledgeStore.files.length === 0"
            class="text-center text-caption text-medium-emphasis py-6"
          >
            <v-icon
              icon="mdi-database-outline"
              size="32"
              class="mb-2"
            />
            <div>知识库还没有文件</div>
            <div class="mt-1">在「工作区文件」Tab 点 + 加入</div>
          </div>
        </div>
      </v-window-item>

      <!-- 节点详情 Tab -->
      <v-window-item value="card">
        <div class="aside-scroll">
          <div class="px-3 py-3">
            <!-- 活跃 Agent -->
            <v-card
              v-if="activeAgent"
              variant="flat"
              rounded="md"
              class="aside-info-card aside-info-card--warning pa-3 mb-3"
            >
              <div class="d-flex align-center mb-2">
                <v-icon icon="mdi-flash" size="18" class="mr-2" />
                <span class="text-subtitle-2 font-weight-bold flex-fill">
                  活跃 Agent
                </span>
                <v-btn
                  size="x-small"
                  icon="mdi-close"
                  variant="text"
                  @click="$emit('dismissAgent')"
                />
              </div>
              <div class="text-body-2 mb-1">{{ activeAgent.title }}</div>
              <div class="text-caption text-medium-emphasis">
                phase: {{ activeAgent.phase }} · worker:
                {{ activeAgent.worker || "—" }}
              </div>
              <v-progress-linear
                :model-value="activeAgent.progress * 100"
                color="warning"
                height="4"
                rounded
                class="mt-2"
              />
            </v-card>

            <!-- 选中卡片详情 -->
            <v-card
              v-if="selectedCard"
              variant="flat"
              rounded="md"
              class="aside-info-card pa-3 mb-3"
            >
              <div class="d-flex align-center mb-2">
                <v-icon
                  :icon="selectedCard.icon || 'mdi-card-text-outline'"
                  size="18"
                  class="mr-2"
                />
                <span class="text-subtitle-2 font-weight-bold flex-fill">
                  {{ selectedCard.title || "卡片详情" }}
                </span>
                <v-btn
                  size="x-small"
                  icon="mdi-close"
                  variant="text"
                  @click="$emit('clearCard')"
                />
              </div>
              <div class="text-body-2 text-medium-emphasis">
                {{ selectedCard.detail || "暂无详情" }}
              </div>
            </v-card>

            <!-- 空态 -->
            <div
              v-if="!activeAgent && !selectedCard"
              class="text-center text-caption text-medium-emphasis py-12"
            >
              <v-icon icon="mdi-card-search-outline" size="32" class="mb-2" />
              <div>点击文档中的 AI 卡片</div>
              <div class="mt-1">详情会在这里展示</div>
            </div>
          </div>
        </div>
      </v-window-item>
    </v-window>
  </v-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useWorkspaceStore } from "@/stores/workspaceStore";
import type { Tile } from "@/stores/workspaceStore";
import { useKnowledgeStore } from "@/stores/knowledgeStore";
import { useOrchestratorStore } from "@/stores/orchestratorStore";
import { useSnackbarStore } from "@/stores/snackbarStore";

interface ActiveAgent {
  title: string;
  phase: string;
  worker?: string;
  progress: number;
}

interface SelectedCard {
  title?: string;
  icon?: string;
  detail?: string;
}

const props = defineProps<{
  activeAgent?: ActiveAgent | null;
  selectedCard?: SelectedCard | null;
}>();

defineEmits<{
  (e: "dismissAgent"): void;
  (e: "clearCard"): void;
  (e: "inspectFile", tile: Tile): void;
}>();

const workspaceStore = useWorkspaceStore();
const knowledgeStore = useKnowledgeStore();
const orchestratorStore = useOrchestratorStore();
const snackbarStore = useSnackbarStore();
const activeTab = ref<"files" | "card" | "knowledge">("files");
const ingesting = ref<Record<string, boolean>>({});

const fileTiles = computed(() =>
  workspaceStore.tiles.filter((t) => t.kind === "file")
);

onMounted(async () => {
  if (orchestratorStore.isLive && knowledgeStore.courseId) {
    knowledgeStore.refreshFiles().catch(() => undefined);
  }
});

const ensureCourseAndRefresh = async () => {
  if (!orchestratorStore.isLive) {
    snackbarStore.showErrorMessage("后端未连接，无法访问知识库");
    return;
  }
  try {
    await knowledgeStore.ensureDefaultCourse();
    await knowledgeStore.refreshFiles();
    snackbarStore.showSuccessMessage("知识库已就绪");
  } catch (e) {
    snackbarStore.showErrorMessage(`知识库初始化失败：${(e as Error).message}`);
  }
};

const ingestTile = async (tile: Tile) => {
  if (!orchestratorStore.isLive) {
    snackbarStore.showErrorMessage("后端未连接");
    return;
  }
  if (tile.source?.kind !== "file") return;
  const root = workspaceStore.root;
  if (!root) {
    snackbarStore.showErrorMessage("工作区路径未就绪");
    return;
  }
  ingesting.value[tile.id] = true;
  try {
    const sep = root.includes("/") ? "/" : "\\";
    const absolutePath = root.endsWith(sep)
      ? root + tile.source.relPath
      : root + sep + tile.source.relPath;
    const res: any = await knowledgeStore.ingestFile({
      absolutePath,
      fileName: tile.source.originalName || tile.title,
    });
    const chunks = res?.chunkCount || res?.chunks || 0;
    const status = res?.status || "success";
    if (status === "success") {
      snackbarStore.showSuccessMessage(
        `已入库：${tile.title}${chunks ? ` · ${chunks} chunks` : ""}`
      );
    } else {
      snackbarStore.showErrorMessage(
        `入库失败：${tile.title}${res?.parseError ? `（${res.parseError}）` : ""}`
      );
    }
  } catch (e) {
    snackbarStore.showErrorMessage(`入库失败：${(e as Error).message}`);
  } finally {
    ingesting.value[tile.id] = false;
  }
};

const fileSubtitle = (file: { fileExt?: string; createdAt?: string }) => {
  const parts: string[] = [];
  if (file.fileExt) parts.push(file.fileExt.toUpperCase());
  if (file.createdAt) parts.push(file.createdAt.slice(5, 16).replace("T", " "));
  return parts.join(" · ") || "已入库";
};

const parseStatusColor = (status?: string) => {
  switch (status) {
    case "success":
      return "success";
    case "failed":
    case "error":
      return "error";
    case "processing":
    case "pending":
      return "warning";
    default:
      return "success";
  }
};

const parseStatusLabel = (status?: string) => {
  switch (status) {
    case "failed":
    case "error":
      return "解析失败";
    case "processing":
      return "处理中";
    case "pending":
      return "排队中";
    default:
      return status || "未知";
  }
};

const iconForExt = (ext?: string) => {
  switch ((ext || "").toLowerCase().replace(".", "")) {
    case "pdf":
      return "mdi-file-pdf-box";
    case "pptx":
    case "ppt":
      return "mdi-file-powerpoint-box";
    case "docx":
    case "doc":
      return "mdi-file-word-box";
    case "md":
      return "mdi-language-markdown";
    case "txt":
      return "mdi-text-box-outline";
    case "png":
    case "jpg":
    case "jpeg":
      return "mdi-image-outline";
    default:
      return "mdi-file-document-outline";
  }
};

watch(
  () => [props.activeAgent, props.selectedCard],
  ([a, c]) => {
    if (a || c) activeTab.value = "card";
  }
);

const iconFor = (tile: Tile) => {
  if (tile.source?.kind !== "file") return "mdi-file-outline";
  switch (tile.source.ext) {
    case "pdf":
      return "mdi-file-pdf-box";
    case "pptx":
    case "ppt":
      return "mdi-file-powerpoint-box";
    case "docx":
    case "doc":
      return "mdi-file-word-box";
    case "xlsx":
    case "xls":
      return "mdi-file-excel-box";
    case "md":
      return "mdi-language-markdown";
    case "png":
    case "jpg":
    case "jpeg":
    case "gif":
    case "webp":
    case "bmp":
      return "mdi-image-outline";
    default:
      return "mdi-file-outline";
  }
};

const colorFor = (tile: Tile) => {
  if (tile.source?.kind !== "file") return "grey";
  switch (tile.source.ext) {
    case "pdf":
      return "red";
    case "pptx":
    case "ppt":
      return "orange";
    case "docx":
    case "doc":
      return "blue";
    case "xlsx":
    case "xls":
      return "green";
    case "md":
      return "purple";
    default:
      return "grey-darken-1";
  }
};

const subtitleFor = (tile: Tile) => {
  if (tile.source?.kind !== "file") return "";
  const sizeKb = (tile.source.size / 1024).toFixed(1);
  return `${tile.source.ext.toUpperCase()} · ${sizeKb} KB`;
};

</script>

<style scoped lang="scss">

</style>
