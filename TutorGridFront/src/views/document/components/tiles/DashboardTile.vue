<!--
  F15: 工作区仪表板磁贴
  - 课程概览：文件数、RAG知识库状态
  - 学习进度：掌握度概览
  - 数据来源：knowledgeStore + /api/profile/mastery
-->
<template>
  <v-card class="dashboard-tile fill-height" variant="flat" rounded="lg">
    <div class="tile-inner d-flex flex-column">
      <!-- 标题行 -->
      <div class="d-flex align-center gap-2 mb-2">
        <v-icon icon="mdi-view-dashboard-outline" color="primary" size="18" />
        <span class="text-caption font-weight-bold text-grey-darken-1">工作区概览</span>
      </div>

      <!-- 课程信息 -->
      <div class="mb-2">
        <div class="text-body-2 font-weight-medium text-truncate">
          {{ courseName }}
        </div>
        <div class="text-caption text-grey-darken-1">
          课程 · {{ fileCount }} 个文件
        </div>
      </div>

      <!-- 知识库状态 -->
      <div class="stat-row d-flex align-center gap-2 mb-1">
        <v-icon :icon="kbIcon" :color="kbColor" size="14" />
        <span class="text-caption flex-fill">知识库</span>
        <v-chip size="x-small" :color="kbColor" variant="tonal">
          {{ kbLabel }}
        </v-chip>
      </div>

      <!-- 文件分块统计 -->
      <div class="stat-row d-flex align-center gap-2 mb-2">
        <v-icon icon="mdi-file-document-multiple-outline" color="indigo" size="14" />
        <span class="text-caption flex-fill">已索引分块</span>
        <span class="text-caption font-weight-medium">{{ totalChunks }}</span>
      </div>

      <!-- 学习进度 -->
      <div class="mt-auto">
        <div class="d-flex align-center justify-space-between mb-1">
          <span class="text-caption text-grey-darken-1">学习进度</span>
          <span class="text-caption font-weight-medium">{{ masteryPercent }}%</span>
        </div>
        <v-progress-linear
          :model-value="masteryPercent"
          :color="masteryColor"
          height="8"
          rounded
        />
        <div class="d-flex justify-space-between mt-1">
          <span class="text-caption text-grey-darken-1">
            已掌握 {{ masteredCount }}/{{ masteryTotal }} 个知识点
          </span>
        </div>
      </div>
    </div>
  </v-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useKnowledgeStore } from "@/stores/knowledgeStore";

const knowledgeStore = useKnowledgeStore();

// ── 知识库数据 ──
const courseName = computed(() => knowledgeStore.courseName || "未创建课程");
const fileCount = computed(() => knowledgeStore.files.length);
const totalChunks = computed(() =>
  knowledgeStore.files.reduce((sum, f) => sum + (f.chunkCount || 0), 0)
);
const kbReady = computed(() => totalChunks.value > 0);
const kbLabel = computed(() => (kbReady.value ? "就绪" : "待入库"));
const kbIcon = computed(() => (kbReady.value ? "mdi-check-circle" : "mdi-alert-circle-outline"));
const kbColor = computed(() => (kbReady.value ? "success" : "warning"));

// ── 学习进度（mock + API） ──
const masteryTotal = ref(12);
const masteredCount = ref(0);
const loadingMastery = ref(false);

const masteryPercent = computed(() => {
  if (masteryTotal.value === 0) return 0;
  return Math.round((masteredCount.value / masteryTotal.value) * 100);
});

const masteryColor = computed(() => {
  if (masteryPercent.value >= 80) return "success";
  if (masteryPercent.value >= 40) return "warning";
  return "grey";
});

// 尝试从后端获取掌握度数据
async function loadMastery() {
  if (loadingMastery.value) return;
  loadingMastery.value = true;
  try {
    const res = await fetch("http://127.0.0.1:8000/api/profile/mastery?limit=200");
    if (res.ok) {
      const data = await res.json();
      const items = Array.isArray(data) ? data : data.items || [];
      if (items.length > 0) {
        masteryTotal.value = items.length;
        masteredCount.value = items.filter((item: any) => {
          const m = typeof item.mastery === "number" ? item.mastery : parseFloat(item.mastery);
          return m >= 0.6;
        }).length;
      }
    }
  } catch {
    // API 不可用时使用 mock 进度
    masteryTotal.value = 8;
    masteredCount.value = 4;
  } finally {
    loadingMastery.value = false;
  }
}

onMounted(async () => {
  try {
    await knowledgeStore.ensureDefaultCourse();
    await knowledgeStore.refreshFiles();
  } catch {
    // 后端不可用时不报错，显示默认状态
  }
  loadMastery();
});
</script>

<style scoped lang="scss">
@use "./_styles" as t;

.dashboard-tile {
  @include t.frosted-tile;
  @include t.tile-padding;
  height: 100%;

  .tile-inner {
    height: 100%;
    min-height: 0;
    overflow: hidden;
  }
}

.stat-row {
  padding: 3px 0;
}
</style>
