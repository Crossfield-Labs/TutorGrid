<!--
  Artifact list inside the OrchestrationDrawer.
  Lists files Codex / OpenCode / python_runner created in scratch/tasks/<task_id>/.
  PNG/JPG show inline thumbnails (resolved via Electron file:// when running in
  the desktop shell, otherwise fall back to filename only).
-->
<template>
  <div class="artifact-list">
    <div v-if="!items.length" class="artifact-list__empty text-medium-emphasis text-caption pa-4 text-center">
      还没有产物，任务跑完之后这里会列出 Codex 创建的文件。
    </div>
    <v-list v-else density="comfortable" lines="two">
      <v-list-item
        v-for="item in items"
        :key="item.path"
        class="artifact-list__item"
        @click="onOpen(item)"
      >
        <template #prepend>
          <div class="artifact-list__thumb">
            <img
              v-if="item.thumbnailUrl"
              :src="item.thumbnailUrl"
              :alt="item.path"
              class="artifact-list__img"
            />
            <v-icon v-else :icon="iconForPath(item.path)" size="28" :color="colorForPath(item.path)" />
          </div>
        </template>

        <v-list-item-title class="text-body-2 font-weight-medium">
          {{ basename(item.path) }}
        </v-list-item-title>
        <v-list-item-subtitle class="text-caption">
          {{ item.path }}<span v-if="item.changeType" class="ml-2 text-medium-emphasis">· {{ item.changeType }}</span>
        </v-list-item-subtitle>

        <template #append>
          <v-btn
            size="x-small"
            variant="text"
            icon="mdi-content-copy"
            @click.stop="onCopyPath(item)"
          />
        </template>
      </v-list-item>
    </v-list>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useSnackbarStore } from "@/stores/snackbarStore";

interface ArtifactRow {
  path: string;
  changeType?: string;
  thumbnailUrl?: string;
}

const props = defineProps<{
  artifacts: Array<Record<string, unknown>>;
  workspace?: string;
}>();

const snackbar = useSnackbarStore();

const items = computed<ArtifactRow[]>(() => {
  const list = props.artifacts || [];
  return list.map((raw) => {
    const path = String(raw.path || raw.name || "");
    const changeType = String(raw.change_type || raw.changeType || "");
    return {
      path,
      changeType,
      thumbnailUrl: thumbnailUrl(path),
    };
  });
});

function thumbnailUrl(path: string): string {
  if (!path) return "";
  const ext = path.split(".").pop()?.toLowerCase() || "";
  if (!["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(ext)) return "";
  // Inside Electron we can serve task workspace files directly via file://
  if (props.workspace && typeof window !== "undefined" && window.location.protocol === "file:") {
    const sep = props.workspace.endsWith("/") || props.workspace.endsWith("\\") ? "" : "/";
    return `file:///${(props.workspace + sep + path).replace(/\\/g, "/")}`;
  }
  return "";
}

function iconForPath(path: string): string {
  const ext = path.split(".").pop()?.toLowerCase() || "";
  if (["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(ext)) return "mdi-image-outline";
  if (["py"].includes(ext)) return "mdi-language-python";
  if (["js", "ts", "tsx", "jsx"].includes(ext)) return "mdi-language-javascript";
  if (["json"].includes(ext)) return "mdi-code-json";
  if (["md", "markdown"].includes(ext)) return "mdi-language-markdown-outline";
  if (["csv", "tsv"].includes(ext)) return "mdi-table";
  if (["txt", "log"].includes(ext)) return "mdi-text-box-outline";
  return "mdi-file-outline";
}

function colorForPath(path: string): string {
  const ext = path.split(".").pop()?.toLowerCase() || "";
  if (["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(ext)) return "primary";
  if (["py"].includes(ext)) return "info";
  if (["md"].includes(ext)) return "secondary";
  return "grey";
}

function basename(path: string): string {
  const idx = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
  return idx >= 0 ? path.slice(idx + 1) : path;
}

function onOpen(item: ArtifactRow) {
  // If the desktop bridge exposes an opener, use it; otherwise just preview path.
  const electron = (window as unknown as { electronAPI?: { openPath?: (p: string) => void } }).electronAPI;
  const fullPath = props.workspace
    ? `${props.workspace}${props.workspace.endsWith("/") || props.workspace.endsWith("\\") ? "" : "/"}${item.path}`
    : item.path;
  if (electron?.openPath) {
    electron.openPath(fullPath);
    return;
  }
  // Web fallback: copy path so user can paste it into their tools
  navigator.clipboard?.writeText(fullPath).then(() => {
    snackbar.showInfoMessage?.(`路径已复制：${fullPath}`);
  });
}

function onCopyPath(item: ArtifactRow) {
  const fullPath = props.workspace
    ? `${props.workspace}${props.workspace.endsWith("/") || props.workspace.endsWith("\\") ? "" : "/"}${item.path}`
    : item.path;
  navigator.clipboard?.writeText(fullPath).then(() => {
    snackbar.showInfoMessage?.(`路径已复制`);
  });
}
</script>

<style scoped lang="scss">
.artifact-list {
  &__thumb {
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    background: rgba(var(--v-theme-on-surface), 0.04);
    overflow: hidden;
    margin-right: 12px;
  }
  &__img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}
</style>
