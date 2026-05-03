<script setup lang="ts">
import { ref, watch } from "vue";
import { useProjectStore, type Project } from "@/stores/projectStore";
import { useSnackbarStore } from "@/stores/snackbarStore";

const props = defineProps<{
  modelValue: boolean;
  project: Project | null;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "saved"): void;
}>();

const projectStore = useProjectStore();
const snackbar = useSnackbarStore();

const name = ref("");
const fsRoot = ref("");
const topBarBg = ref("");
const pageBg = ref("");
const sidebarColor = ref("");
const topBarPreview = ref("");
const pagePreview = ref("");

const submitting = ref(false);
const uploadingTopBar = ref(false);
const uploadingPage = ref(false);

const topBarFileInput = ref<HTMLInputElement | null>(null);
const pageFileInput = ref<HTMLInputElement | null>(null);

watch(
  () => props.modelValue,
  (open) => {
    if (open && props.project) {
      name.value = props.project.name;
      fsRoot.value = props.project.fsRoot;
      topBarBg.value = props.project.appearance.topBarBg || "";
      pageBg.value = props.project.appearance.pageBg || "";
      sidebarColor.value = props.project.appearance.sidebarColor || "";
      revokePreviews();
      topBarPreview.value = "";
      pagePreview.value = "";
    }
  }
);

function revokePreviews() {
  if (topBarPreview.value.startsWith("blob:"))
    URL.revokeObjectURL(topBarPreview.value);
  if (pagePreview.value.startsWith("blob:"))
    URL.revokeObjectURL(pagePreview.value);
}

const isElectron =
  typeof window !== "undefined" && Boolean(window.metaAgent?.workspace);

async function handleAssetPick(event: Event, kind: "topBar" | "page") {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  if (!isElectron) {
    snackbar.showWarningMessage("仅 Electron 环境支持上传图片");
    input.value = "";
    return;
  }
  const setLoading = kind === "topBar" ? uploadingTopBar : uploadingPage;
  setLoading.value = true;
  try {
    const arrayBuffer = await file.arrayBuffer();
    const buffer = new Uint8Array(arrayBuffer);
    const { relPath } = await window.metaAgent.workspace.saveAssetTo({
      targetRoot: fsRoot.value,
      buffer,
      originalName: file.name,
    });
    const previewUrl = URL.createObjectURL(file);
    if (kind === "topBar") {
      topBarBg.value = relPath;
      if (topBarPreview.value.startsWith("blob:"))
        URL.revokeObjectURL(topBarPreview.value);
      topBarPreview.value = previewUrl;
    } else {
      pageBg.value = relPath;
      if (pagePreview.value.startsWith("blob:"))
        URL.revokeObjectURL(pagePreview.value);
      pagePreview.value = previewUrl;
    }
  } catch (err) {
    snackbar.showErrorMessage(`上传失败: ${(err as Error).message}`);
  } finally {
    setLoading.value = false;
    input.value = "";
  }
}

function clearAsset(kind: "topBar" | "page") {
  if (kind === "topBar") {
    topBarBg.value = "";
    if (topBarPreview.value.startsWith("blob:"))
      URL.revokeObjectURL(topBarPreview.value);
    topBarPreview.value = "";
  } else {
    pageBg.value = "";
    if (pagePreview.value.startsWith("blob:"))
      URL.revokeObjectURL(pagePreview.value);
    pagePreview.value = "";
  }
}

async function submit() {
  if (!props.project) return;
  if (!name.value.trim()) {
    snackbar.showWarningMessage("请填写工作区名称");
    return;
  }
  submitting.value = true;
  const updated = await projectStore.updateProject(props.project.id, {
    name: name.value.trim(),
    appearance: {
      topBarBg: topBarBg.value.trim(),
      pageBg: pageBg.value.trim(),
      sidebarColor: sidebarColor.value.trim(),
    },
  });
  submitting.value = false;
  if (updated) {
    snackbar.showSuccessMessage("已保存");
    revokePreviews();
    emit("saved");
    emit("update:modelValue", false);
  }
}

function cancel() {
  revokePreviews();
  emit("update:modelValue", false);
}
</script>

<template>
  <v-dialog
    :model-value="modelValue"
    max-width="600"
    persistent
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <v-card>
      <v-card-title class="d-flex align-center pa-4">
        <v-icon icon="mdi-folder-edit-outline" class="mr-2" />
        编辑工作区
      </v-card-title>
      <v-divider />

      <v-card-text class="pa-4">
        <v-text-field
          v-model="name"
          label="工作区名称"
          variant="outlined"
          density="comfortable"
          autofocus
          class="mb-3"
        />

        <v-text-field
          :model-value="fsRoot"
          label="本地目录（不可修改）"
          variant="outlined"
          density="comfortable"
          readonly
          disabled
          hide-details
          class="mb-3"
        />

        <div class="text-overline mt-4 mb-2">视觉外观</div>

        <!-- 顶部 AppBar 背景图 -->
        <div class="mb-4">
          <div class="text-caption text-medium-emphasis mb-2">
            顶部 AppBar 背景图
          </div>
          <input
            ref="topBarFileInput"
            type="file"
            accept="image/*"
            hidden
            @change="(e) => handleAssetPick(e, 'topBar')"
          />
          <div class="d-flex align-center ga-2">
            <v-btn
              variant="tonal"
              prepend-icon="mdi-image-plus-outline"
              :loading="uploadingTopBar"
              @click="topBarFileInput?.click()"
            >
              {{ topBarBg ? "重新选图" : "上传图片" }}
            </v-btn>
            <v-img
              v-if="topBarPreview"
              :src="topBarPreview"
              width="120"
              height="40"
              cover
              class="rounded"
            />
            <v-btn
              v-if="topBarBg"
              size="small"
              variant="text"
              icon="mdi-close-circle"
              @click="clearAsset('topBar')"
            />
          </div>
          <div v-if="topBarBg" class="text-caption text-medium-emphasis mt-1">
            当前: {{ topBarBg }}
          </div>
        </div>

        <!-- 整页背景图 -->
        <div class="mb-4">
          <div class="text-caption text-medium-emphasis mb-2">整页背景图</div>
          <input
            ref="pageFileInput"
            type="file"
            accept="image/*"
            hidden
            @change="(e) => handleAssetPick(e, 'page')"
          />
          <div class="d-flex align-center ga-2">
            <v-btn
              variant="tonal"
              prepend-icon="mdi-image-plus-outline"
              :loading="uploadingPage"
              @click="pageFileInput?.click()"
            >
              {{ pageBg ? "重新选图" : "上传图片" }}
            </v-btn>
            <v-img
              v-if="pagePreview"
              :src="pagePreview"
              width="120"
              height="40"
              cover
              class="rounded"
            />
            <v-btn
              v-if="pageBg"
              size="small"
              variant="text"
              icon="mdi-close-circle"
              @click="clearAsset('page')"
            />
          </div>
          <div v-if="pageBg" class="text-caption text-medium-emphasis mt-1">
            当前: {{ pageBg }}
          </div>
        </div>

        <v-text-field
          v-model="sidebarColor"
          label="Sidebar 色块（CSS 颜色值）"
          placeholder="#d7e7ba 或 rgba(...)"
          variant="outlined"
          density="comfortable"
          hint="Sidebar 折叠列表上的色块"
          persistent-hint
        />
      </v-card-text>

      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="text" :disabled="submitting" @click="cancel">取消</v-btn>
        <v-btn
          color="primary"
          variant="flat"
          :loading="submitting"
          @click="submit"
        >
          保存
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
