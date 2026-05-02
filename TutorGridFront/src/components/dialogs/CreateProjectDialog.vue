<script setup lang="ts">
import { ref, watch } from "vue";
import { useProjectStore } from "@/stores/projectStore";
import { useSnackbarStore } from "@/stores/snackbarStore";

const props = defineProps<{
  modelValue: boolean;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "created", projectId: string): void;
}>();

const projectStore = useProjectStore();
const snackbar = useSnackbarStore();

const name = ref("");
const fsRoot = ref("");
// 这里存的是 .assets/xxx.jpg 相对路径（保存到 SQLite 的 appearance.topBarBg / pageBg）
const topBarBg = ref("");
const pageBg = ref("");
const sidebarColor = ref("");
// 本地预览 blob URL（仅 dialog 内显示用，提交后被 created 事件接管）
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
    if (open) {
      name.value = "";
      fsRoot.value = "";
      topBarBg.value = "";
      pageBg.value = "";
      sidebarColor.value = "";
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

async function pickFolder() {
  if (!isElectron) {
    snackbar.showWarningMessage("仅 Electron 环境支持选择本地目录");
    return;
  }
  try {
    const picked = await window.metaAgent.workspace.pickFolder();
    if (picked) fsRoot.value = picked;
  } catch (err) {
    snackbar.showErrorMessage(`选择目录失败: ${(err as Error).message}`);
  }
}

async function handleAssetPick(
  event: Event,
  kind: "topBar" | "page"
): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  if (!fsRoot.value) {
    snackbar.showWarningMessage("请先选择本地目录（图片会复制到该目录的 .assets/ 子目录）");
    input.value = "";
    return;
  }
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
    // 本地预览：直接用刚选的 File 生成 blob URL（避免再走一次 IPC 读）
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
  if (!name.value.trim()) {
    snackbar.showWarningMessage("请填写工作区名称");
    return;
  }
  if (!fsRoot.value.trim()) {
    snackbar.showWarningMessage("请选择本地目录");
    return;
  }
  submitting.value = true;
  const created = await projectStore.createProject({
    name: name.value,
    fsRoot: fsRoot.value,
    appearance: {
      topBarBg: topBarBg.value.trim(),
      pageBg: pageBg.value.trim(),
      sidebarColor: sidebarColor.value.trim(),
    },
  });
  submitting.value = false;
  if (created) {
    revokePreviews();
    emit("created", created.id);
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
        <v-icon icon="mdi-folder-plus-outline" class="mr-2" />
        新建工作区
      </v-card-title>
      <v-divider />

      <v-card-text class="pa-4">
        <v-text-field
          v-model="name"
          label="工作区名称"
          placeholder="如：数据挖掘 / 机器学习"
          variant="outlined"
          density="comfortable"
          autofocus
          class="mb-3"
        />

        <div class="d-flex align-center ga-2 mb-3">
          <v-text-field
            v-model="fsRoot"
            label="本地目录（Hyperdoc 文件存放路径）"
            placeholder="点右侧按钮选择"
            variant="outlined"
            density="comfortable"
            readonly
            hide-details
          />
          <v-btn
            color="primary"
            variant="tonal"
            prepend-icon="mdi-folder-search-outline"
            :disabled="!isElectron"
            @click="pickFolder"
          >
            选择目录
          </v-btn>
        </div>

        <v-expansion-panels variant="accordion" class="mb-1">
          <v-expansion-panel>
            <v-expansion-panel-title>
              <v-icon icon="mdi-palette-outline" class="mr-2" size="20" />
              视觉外观（可选）
            </v-expansion-panel-title>
            <v-expansion-panel-text>
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
                    :disabled="!fsRoot"
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
                  存到: {{ topBarBg }}
                </div>
              </div>

              <!-- 整页背景图 -->
              <div class="mb-4">
                <div class="text-caption text-medium-emphasis mb-2">
                  整页背景图
                </div>
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
                    :disabled="!fsRoot"
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
                  存到: {{ pageBg }}
                </div>
              </div>

              <v-text-field
                v-model="sidebarColor"
                label="Sidebar 色块（CSS 颜色值，可选）"
                placeholder="#d7e7ba 或 rgba(...)"
                variant="outlined"
                density="comfortable"
                hint="Sidebar 折叠列表上的色块（识别工作区用）"
                persistent-hint
              />
              <div
                v-if="!fsRoot"
                class="text-caption text-warning mt-3"
              >
                提示：请先选择本地目录后再上传图片（图片会复制到该目录的 .assets/ 下）
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
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
          创建
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
