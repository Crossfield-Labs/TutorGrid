<template>
  <v-card
    class="pa-5 mt-4 card-shadow tile-card"
    @dblclick.stop="onPrimaryOpen"
    @click.stop="onTileClick"
  >
    <div class="d-flex align-start font-weight-bold text-title">
      <v-icon :icon="tileIcon" :color="tileIconColor" size="18" class="mr-1 mt-n1" />
      <span class="flex-fill">{{ tile.title }}</span>
      <v-chip
        v-if="isMissing"
        color="error"
        size="x-small"
        variant="tonal"
        class="mr-1"
      >
        <v-icon icon="mdi-link-off" size="12" class="mr-1" />
        文件丢失
      </v-chip>
      <v-menu location="bottom end" transition="slide-x-transition" @click.stop>
        <template #activator="{ props }">
          <v-btn
            v-bind="props"
            size="small"
            icon="mdi-dots-vertical"
            variant="text"
            rounded
            color="primary"
            class="my-n2"
          />
        </template>
        <v-list density="compact">
          <v-list-item @click.stop="$emit('edit')">
            <v-list-item-title>
              <v-icon icon="mdi-pencil" size="16" class="mr-1" />
              编辑
            </v-list-item-title>
          </v-list-item>
          <v-list-item v-if="canOpenExternal" @click.stop="onOpenExternal">
            <v-list-item-title>
              <v-icon icon="mdi-open-in-app" size="16" class="mr-1" />
              用系统应用打开
            </v-list-item-title>
          </v-list-item>
          <v-list-item @click.stop="$emit('delete')">
            <v-list-item-title>
              <v-icon icon="mdi-delete" size="16" class="mr-1" />
              删除
            </v-list-item-title>
          </v-list-item>
        </v-list>
      </v-menu>
    </div>

    <!-- 说明 / 摘要 -->
    <div v-if="tile.description" class="text-content mt-2 text-body-2">
      {{ tile.description }}
    </div>

    <!-- 附件区（位于说明之下）-->
    <!-- Hyper 文档 -->
    <div v-if="tile.kind === 'hyperdoc'" class="mt-3">
      <v-card
        variant="outlined"
        class="d-flex align-center pa-3 cursor-pointer hyperdoc-block"
        @click.stop="onPrimaryOpen"
      >
        <v-icon icon="mdi-file-document-edit-outline" color="primary" size="24" class="mr-3" />
        <div class="flex-fill">
          <div class="font-weight-medium">Hyper 文档</div>
          <div class="text-caption text-grey">双击进入 TipTap 编辑</div>
        </div>
        <v-icon icon="mdi-arrow-top-right" color="primary" />
      </v-card>
    </div>

    <!-- 图片 -->
    <div v-else-if="isImage" class="mt-3">
      <v-img
        v-if="blobUrl"
        :src="blobUrl"
        @click.stop="showImageDialog = true"
        :aspect-ratio="16 / 9"
        cover
        class="rounded cursor-pointer"
        style="max-height: 200px"
      />
      <div v-else class="d-flex align-center justify-center" style="height: 100px">
        <v-progress-circular indeterminate size="20" color="primary" />
      </div>
    </div>

    <!-- PDF -->
    <div v-else-if="isPdf" class="mt-3">
      <v-card
        variant="outlined"
        @click.stop="$emit('previewPdf', tile)"
        class="d-flex align-center pa-3 cursor-pointer"
      >
        <v-icon icon="mdi-file-pdf-box" color="red" size="24" class="mr-3" />
        <div class="flex-fill">
          <div class="font-weight-medium">{{ originalName }}</div>
          <div class="text-caption text-grey">点击预览 PDF</div>
        </div>
        <v-icon icon="mdi-eye" color="primary" />
      </v-card>
    </div>

    <!-- 其它文件（PPT/Word/Excel/MD/...） -->
    <div v-else-if="tile.kind === 'file'" class="mt-3">
      <v-card
        variant="outlined"
        @click.stop="onOpenExternal"
        class="d-flex align-center pa-3 cursor-pointer"
      >
        <v-icon :icon="fileIcon" :color="fileColor" size="24" class="mr-3" />
        <div class="flex-fill">
          <div class="font-weight-medium text-truncate">{{ originalName }}</div>
          <div class="text-caption text-grey">{{ fileLabel }} · 点击用系统应用打开</div>
        </div>
        <v-icon icon="mdi-open-in-app" color="primary" />
      </v-card>
    </div>

    <!-- 图片放大预览 -->
    <v-dialog v-model="showImageDialog" max-width="800">
      <v-card>
        <v-card-title class="d-flex align-center">
          <span class="flex-fill">{{ originalName }}</span>
          <v-btn icon="mdi-close" variant="text" @click="showImageDialog = false" />
        </v-card-title>
        <v-card-text class="pa-0">
          <v-img v-if="blobUrl" :src="blobUrl" contain />
        </v-card-text>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import type { Tile } from "@/stores/workspaceStore";
import { useWorkspaceStore } from "@/stores/workspaceStore";

const props = defineProps<{ tile: Tile }>();
const emit = defineEmits<{
  (e: "edit"): void;
  (e: "delete"): void;
  (e: "previewPdf", tile: Tile): void;
}>();

const router = useRouter();
const workspaceStore = useWorkspaceStore();
const showImageDialog = ref(false);
const blobUrl = ref<string | null>(null);

const isMissing = computed(() => Boolean(workspaceStore.missing[props.tile.id]));

const tileIcon = computed(() => {
  switch (props.tile.kind) {
    case "hyperdoc": return "mdi-file-document-edit-outline";
    case "file": return "mdi-file-outline";
    case "note": return "mdi-note-text-outline";
    default: return "mdi-card-outline";
  }
});

const tileIconColor = computed(() => {
  switch (props.tile.kind) {
    case "hyperdoc": return "primary";
    case "file": return "orange";
    case "note": return "grey-darken-1";
    default: return "grey";
  }
});

const isImage = computed(
  () =>
    props.tile.kind === "file" &&
    props.tile.source?.kind === "file" &&
    workspaceStore.isImage(props.tile.source.ext)
);

const isPdf = computed(
  () =>
    props.tile.kind === "file" &&
    props.tile.source?.kind === "file" &&
    props.tile.source.ext === "pdf"
);

const originalName = computed(() => {
  const s = props.tile.source;
  return s?.kind === "file" ? s.originalName : "";
});

const canOpenExternal = computed(
  () => props.tile.kind === "file" && props.tile.source?.kind === "file"
);

const fileIcon = computed(() => {
  if (props.tile.source?.kind !== "file") return "mdi-file-outline";
  switch (props.tile.source.ext) {
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
    case "txt":
      return "mdi-file-document-outline";
    default:
      return "mdi-file-outline";
  }
});

const fileColor = computed(() => {
  if (props.tile.source?.kind !== "file") return "grey";
  switch (props.tile.source.ext) {
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
      return "grey";
  }
});

const fileLabel = computed(() => {
  if (props.tile.source?.kind !== "file") return "";
  return props.tile.source.ext.toUpperCase();
});

const loadImage = async () => {
  if (!isImage.value || props.tile.source?.kind !== "file") return;
  blobUrl.value = await workspaceStore.getBlobURL(
    props.tile.source.relPath,
    props.tile.source.mime
  );
};

let clickTimer: ReturnType<typeof setTimeout> | null = null;

const onTileClick = () => {
  // 只对 note 类型磁贴响应单击（其他类型有自己的内部点击区域）
  if (props.tile.kind !== "note") return;
  // 防止双击时触发两次
  if (clickTimer) {
    clearTimeout(clickTimer);
    clickTimer = null;
    return;
  }
  clickTimer = setTimeout(() => {
    clickTimer = null;
    emit("edit");
  }, 250);
};

const onPrimaryOpen = () => {
  // 取消可能待处理的单击
  if (clickTimer) {
    clearTimeout(clickTimer);
    clickTimer = null;
  }
  if (props.tile.kind === "hyperdoc") {
    router.push(`/hyperdoc/${props.tile.id}`);
  } else if (isPdf.value) {
    emit('previewPdf', props.tile);
  } else if (isImage.value) {
    showImageDialog.value = true;
  } else if (canOpenExternal.value) {
    onOpenExternal();
  } else if (props.tile.kind === "note") {
    // note 类型：双击打开编辑对话框
    emit('edit');
  }
};

const onOpenExternal = () => {
  if (props.tile.source?.kind === "file") {
    workspaceStore.openExternal(props.tile.source.relPath);
  }
};

onMounted(loadImage);
watch(
  () => props.tile.source,
  () => {
    blobUrl.value = null;
    loadImage();
  }
);
</script>

<style scoped>
.card-shadow {
  box-shadow: 0 2px 8px rgba(99, 99, 99, 0.2) !important;
  user-select: none;
  cursor: move;
}

.card-shadow:hover {
  box-shadow: 0 4px 12px rgba(99, 99, 99, 0.3) !important;
}

.sortable-drag .card-shadow {
  cursor: grabbing !important;
}

.cursor-pointer {
  cursor: pointer;
}

.hyperdoc-block:hover {
  background: rgba(var(--v-theme-primary), 0.04);
}

.text-content {
  color: rgba(0, 0, 0, 0.7);
  white-space: pre-wrap;
}

.v-btn,
.v-img,
.v-card[variant="outlined"] {
  pointer-events: auto;
}
</style>
