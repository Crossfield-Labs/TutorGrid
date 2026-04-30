<template>
  <v-container>
    <v-card class="mb-4">
      <v-img
        :aspect-ratio="1"
        class="bg-white"
        src="/images/boardbackground.jpg"
        max-height="100px"
        cover
      >
        <div class="d-flex align-center mt-5 ml-2 mr-2 text-white">
          <div class="text-subtitle-2 ml-3">
            <v-icon icon="mdi-folder-outline" color="white" class="mr-1" />
            工作区: {{ workspaceStore.root || '加载中...' }}
          </div>
          <v-spacer></v-spacer>
          <v-btn
            color="white"
            prepend-icon="mdi-database"
            variant="outlined"
            @click="pasteFromDataCenter"
          >
            从数据中心粘贴
          </v-btn>
          <v-btn
            color="white"
            prepend-icon="mdi-lightbulb-import-outline"
            variant="outlined"
            @click="importFromInspiration"
            class="mr-2 ml-2"
          >
            从灵感板导入 ({{ inspirationStore.items.length }})
          </v-btn>
        </div>
      </v-img>
    </v-card>

    <!-- columns -->
    <v-row style="min-width: 800px">
      <v-col
        v-for="column in workspaceStore.columns"
        :key="column"
        cols="3"
        class="pa-4 flex-fill"
      >
        <div class="d-flex align-center">
          <h5 class="font-weight-bold">{{ column }}</h5>
          <v-spacer></v-spacer>
          <v-btn
            variant="text"
            rounded
            icon="mdi-plus"
            size="small"
            color="primary"
            class="mr-n3"
            @click="toggleAddForm(column)"
          />
        </div>

        <!-- 内联新建表单 -->
        <v-card
          v-show="addStates[column]?.visible"
          class="pa-5 my-2"
          elevation="2"
        >
          <v-text-field
            v-if="addStates[column]"
            v-model="addStates[column].title"
            color="primary"
            label="Title"
            variant="underlined"
            hide-details
            placeholder="Input title for this card"
            :autofocus="addStates[column]?.visible"
            @keyup.enter="submitAdd(column)"
            @keyup.esc="closeAddForm(column)"
          />

          <v-switch
            v-if="addStates[column]"
            v-model="addStates[column].asHyperdoc"
            color="primary"
            density="compact"
            hide-details
            class="mt-2"
          >
            <template #label>
              <v-icon
                icon="mdi-file-document-edit-outline"
                size="18"
                class="mr-2"
              />
              <span class="text-body-2">创建为 Hyper 文档</span>
            </template>
          </v-switch>

          <v-file-input
            v-if="addStates[column] && !addStates[column].asHyperdoc"
            v-model="addStates[column].files"
            label="添加附件 (可选)"
            variant="underlined"
            accept=".pdf,.pptx,.ppt,.docx,.doc,.xlsx,.xls,.md,.txt,.png,.jpg,.jpeg,.gif,.webp,.bmp,.svg"
            hide-details
            class="mt-2"
            clearable
            prepend-icon="mdi-paperclip"
          />

          <div class="mt-3 d-flex flex-md-row flex-column">
            <v-btn
              class="flex-fill ma-1"
              size="small"
              @click="closeAddForm(column)"
            >
              Cancel
            </v-btn>
            <v-btn
              class="flex-fill ma-1"
              size="small"
              color="primary"
              :loading="addStates[column]?.submitting"
              :disabled="!addStates[column]?.title?.trim()"
              @click="submitAdd(column)"
            >
              Add
            </v-btn>
          </div>
        </v-card>

        <draggable
          :list="workspaceStore.tilesByColumn[column] || []"
          :group="'tiles'"
          :animation="200"
          ghost-class="ghost"
          class="list-group"
          item-key="id"
          handle=".drag-handle"
          @change="(evt: any) => handleDragChange(evt, column)"
        >
          <template #item="{ element }">
            <div>
              <board-card
                :key="`tile-${element.id}`"
                :tile="element"
                class="board-item my-2 drag-handle"
                @edit="showEdit(element)"
                @delete="showDelete(element)"
                @previewPdf="onPreviewPdf"
              />
            </div>
          </template>
        </draggable>
      </v-col>
    </v-row>
  </v-container>

  <!-- 编辑卡片对话框 -->
  <v-dialog persistent v-model="editDialog" width="600">
    <v-card>
      <v-card-title class="pa-4 d-flex align-center">
        <span class="flex-fill">编辑磁贴</span>
        <v-btn
          variant="text"
          rounded
          icon="mdi-close"
          size="small"
          color="primary"
          class="mr-n3"
          @click="editDialog = false"
        />
      </v-card-title>
      <v-divider />
      <div class="pa-4">
        <v-text-field
          v-model="editTitle"
          label="标题"
          variant="plain"
          hide-details
          autofocus
          class="py-2 px-1"
        />
        <v-divider />
        <v-textarea
          v-model="editDescription"
          label="描述 / 摘要"
          variant="plain"
          hide-details
          auto-grow
          rows="3"
          class="px-2 py-1"
        />
      </div>
      <v-divider />
      <v-card-actions class="pa-4">
        <v-btn variant="outlined" @click="editDialog = false">取消</v-btn>
        <v-spacer />
        <v-btn variant="flat" color="primary" @click="saveEdit">保存</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 删除确认 -->
  <v-dialog v-model="deleteDialog" max-width="320">
    <v-card>
      <v-card-title>删除磁贴</v-card-title>
      <v-card-text>
        确认删除此磁贴？
        <span v-if="cardToDelete?.source" class="text-error d-block mt-2">
          <v-icon icon="mdi-alert-outline" size="16" class="mr-1" />
          关联的本地文件也会被删除
        </span>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="plain" @click="deleteDialog = false">取消</v-btn>
        <v-btn variant="flat" color="error" @click="confirmDelete">删除</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- PDF 预览 -->
  <v-dialog v-model="pdfDialog" max-width="900" max-height="700">
    <v-card>
      <v-card-title class="d-flex align-center">
        <span class="flex-fill">{{ pdfTile?.title }}</span>
        <v-btn icon="mdi-close" variant="text" @click="pdfDialog = false" />
      </v-card-title>
      <v-card-text class="pa-0" style="height: 600px">
        <iframe
          v-if="pdfBlobUrl"
          :src="pdfBlobUrl"
          width="100%"
          height="100%"
          style="border: none"
        />
        <div v-else class="d-flex align-center justify-center fill-height">
          <v-progress-circular indeterminate color="primary" />
        </div>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import draggable from "vuedraggable";
import BoardCard from "@/components/BoardCard.vue";
import { onMounted, reactive, ref, watch } from "vue";
import { useInspirationStore } from "@/stores/inspirationStore";
import { useSnackbarStore } from "@/stores/snackbarStore";
import { useWorkspaceStore } from "@/stores/workspaceStore";
import type { Tile } from "@/stores/workspaceStore";

const snackbarStore = useSnackbarStore();
const inspirationStore = useInspirationStore();
const workspaceStore = useWorkspaceStore();

interface AddState {
  visible: boolean;
  title: string;
  asHyperdoc: boolean;
  files: File[];
  submitting: boolean;
}

const addStates = reactive<Record<string, AddState>>({});

const ensureAddState = (column: string) => {
  if (!addStates[column]) {
    addStates[column] = {
      visible: false,
      title: "",
      asHyperdoc: false,
      files: [],
      submitting: false,
    };
  }
  return addStates[column];
};

const toggleAddForm = (column: string) => {
  const s = ensureAddState(column);
  s.visible = !s.visible;
  if (s.visible) {
    s.title = "";
    s.asHyperdoc = false;
    s.files = [];
  }
};

const closeAddForm = (column: string) => {
  const s = ensureAddState(column);
  s.visible = false;
};

const submitAdd = async (column: string) => {
  const s = ensureAddState(column);
  const title = s.title.trim();
  if (!title || s.submitting) return;
  s.submitting = true;
  try {
    const file = s.files[0];
    if (s.asHyperdoc) {
      await workspaceStore.addHyperdoc(column, title);
      snackbarStore.showSuccessMessage("Hyper 文档已创建");
    } else if (file) {
      await workspaceStore.addFile(column, file, title);
      snackbarStore.showSuccessMessage("文件已导入");
    } else {
      await workspaceStore.addNote(column, title);
      snackbarStore.showSuccessMessage("磁贴已创建");
    }
    s.visible = false;
    s.title = "";
    s.files = [];
    s.asHyperdoc = false;
  } catch (e) {
    console.error(e);
    snackbarStore.showErrorMessage(`创建失败: ${String(e)}`);
  } finally {
    s.submitting = false;
  }
};

// 编辑
const editDialog = ref(false);
const editingTile = ref<Tile | null>(null);
const editTitle = ref("");
const editDescription = ref("");

const showEdit = (tile: Tile) => {
  editingTile.value = tile;
  editTitle.value = tile.title;
  editDescription.value = tile.description ?? "";
  editDialog.value = true;
};

const saveEdit = async () => {
  if (!editingTile.value) return;
  await workspaceStore.updateTile(editingTile.value.id, {
    title: editTitle.value.trim() || editingTile.value.title,
    description: editDescription.value,
  });
  editDialog.value = false;
};

// 删除
const deleteDialog = ref(false);
const cardToDelete = ref<Tile | null>(null);

const showDelete = (tile: Tile) => {
  cardToDelete.value = tile;
  deleteDialog.value = true;
};

const confirmDelete = async () => {
  if (!cardToDelete.value) return;
  await workspaceStore.removeTile(cardToDelete.value.id);
  deleteDialog.value = false;
  cardToDelete.value = null;
  snackbarStore.showSuccessMessage(`已删除`);
};

// 拖拽
const handleDragChange = (evt: any, column: string) => {
  const moved = evt.added || evt.moved;
  if (!moved) return;
  const tileId = moved.element.id;
  const newIndex = moved.newIndex;
  workspaceStore.moveTile(tileId, column, newIndex);
};

// PDF 预览
const pdfDialog = ref(false);
const pdfTile = ref<Tile | null>(null);
const pdfBlobUrl = ref<string | null>(null);

const onPreviewPdf = async (tile: Tile) => {
  if (tile.source?.kind !== "file") return;
  pdfTile.value = tile;
  pdfBlobUrl.value = null;
  pdfDialog.value = true;
  pdfBlobUrl.value = await workspaceStore.getBlobURL(
    tile.source.relPath,
    tile.source.mime || "application/pdf"
  );
};

watch(pdfDialog, (open) => {
  if (!open) {
    pdfTile.value = null;
    pdfBlobUrl.value = null;
  }
});

// 占位逻辑：从数据中心 / 从灵感板（先适配新模型，后面整改）
const pasteFromDataCenter = async () => {
  await workspaceStore.addNote(
    "TODO",
    `数据中心导入 - ${new Date().toLocaleString()}`,
    "从数据中心导入的观测数据"
  );
};

const importFromInspiration = async () => {
  if (inspirationStore.items.length === 0) {
    snackbarStore.showErrorMessage("灵感板暂无内容");
    return;
  }
  for (const item of inspirationStore.items) {
    await workspaceStore.addNote(
      "TODO",
      item.title,
      item.content + (item.subtitle ? `\n\n${item.subtitle}` : "")
    );
  }
  snackbarStore.showSuccessMessage(
    `成功导入 ${inspirationStore.items.length} 个灵感项目到 TODO 列`
  );
};

onMounted(async () => {
  await workspaceStore.init();
  workspaceStore.columns.forEach(ensureAddState);
});
</script>

<style lang="scss" scoped>
.ghost {
  opacity: 0.5;
  background: #c8ebfb;
}

.board-item {
  transition: transform 0.2s;
  user-select: none;
  &:hover {
    transition: transform 0.2s;
    transform: translateY(-3px);
  }
}

.list-group {
  min-height: 100px;
  padding-bottom: 20px;
}

.drag-handle {
  cursor: move;
}
</style>
