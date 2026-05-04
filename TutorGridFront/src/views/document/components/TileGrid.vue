<!--
  F08: 右侧磁贴Grid
  - CSS Grid 原生实现，grid-template-columns: repeat(N, 1fr)
  - 支持 2×2 / 3×3 布局切换
  - 磁贴可跨格：1×1 / 1×2 / 2×2
  - 空格子显示"+" 添加引导
  - 磁贴数据持久化到 Hyper 文档 metadata
-->
<template>
  <div ref="containerRef" class="tile-grid-root">
    <!-- 布局切换工具栏 -->
    <div class="tile-grid-toolbar d-flex align-center justify-space-between mb-2">
      <span class="text-caption text-grey-darken-1 font-weight-medium">
        {{ layoutLabel }}
      </span>
      <v-btn-toggle
        :model-value="gridCols"
        mandatory
        density="compact"
        variant="outlined"
        divided
        @update:model-value="onToggleCols"
      >
        <v-btn :value="2" size="x-small" icon="mdi-grid">2×2</v-btn>
        <v-btn :value="3" size="x-small" icon="mdi-grid-large">3×3</v-btn>
      </v-btn-toggle>
    </div>

    <!-- CSS Grid 容器 -->
    <div
      class="tile-grid-css"
      :style="{
        gridTemplateColumns: `repeat(${gridCols}, 1fr)`,
      }"
    >
      <div
        v-for="tile in tiles"
        :key="tile.id"
        class="tile-cell"
        :class="{ 'tile-empty': tile.kind === 'empty' }"
        :style="{
          gridColumn: `span ${tile.colSpan}`,
          gridRow: `span ${tile.rowSpan}`,
        }"
        @contextmenu.prevent="(e) => onContextMenu(e, tile)"
      >
        <!-- AgentTile -->
        <AgentTile
          v-if="tile.kind === 'agent'"
          :agent="agent"
          @dismiss="emit('dismissAgent')"
        />

        <!-- SelectionTile -->
        <SelectionTile
          v-else-if="tile.kind === 'selection'"
          :card="card"
          @clear="emit('clearCard')"
        />

        <!-- TaskTile -->
        <TaskTile
          v-else-if="tile.kind === 'task'"
          :task="task"
          :starting="taskStarting"
          :size="sizeLabel(tile)"
          @start="(instruction) => emit('startTask', instruction)"
          @resume="(content) => emit('resumeTask', content)"
          @interrupt="emit('interruptTask')"
        />

        <!-- FileTile (F09) -->
        <FileTile
          v-else-if="tile.kind === 'file'"
          :title="tile.title || '文件'"
          :subtitle="tile.subtitle"
          :file-path="tile.filePath"
        />

        <!-- CitationTile (F09) -->
        <CitationTile
          v-else-if="tile.kind === 'citation'"
          :citations="tile.citations"
        />

        <!-- DashboardTile (F15) -->
        <DashboardTile
          v-else-if="tile.kind === 'dashboard'"
        />

        <!-- QuizTile (F14) -->
        <QuizTile
          v-else-if="tile.kind === 'quiz'"
          :quiz="tile.quizData"
        />

        <!-- FlashcardTile (F14) -->
        <FlashcardTile
          v-else-if="tile.kind === 'flashcard'"
          :cards="tile.flashcards"
        />

        <!-- PlaceholderTile -->
        <PlaceholderTile
          v-else-if="tile.kind === 'placeholder'"
          :title="tile.title || '占位'"
          :subtitle="tile.subtitle"
          :icon="tile.icon"
          :icon-color="tile.iconColor"
          :size="sizeLabel(tile)"
        />

        <!-- 空格子："+" 添加按钮 -->
        <div v-else class="empty-slot" @click="emit('addTile', tile.id)">
          <v-icon icon="mdi-plus-circle-outline" size="28" color="grey-lighten-1" />
          <span class="text-caption text-grey">添加磁贴</span>
        </div>
      </div>
    </div>

    <!-- 右键菜单 -->
    <v-menu
      v-model="menuOpen"
      :target="menuTarget"
      :close-on-content-click="true"
      location="end"
    >
      <v-list density="compact" min-width="180" rounded="lg">
        <v-list-subheader class="text-caption">调整大小</v-list-subheader>
        <v-list-item
          v-for="size in SIZE_OPTIONS.filter(s => s.w <= gridCols)"
          :key="size.key"
          :prepend-icon="size.icon"
          :title="size.label"
          :disabled="isCurrentSize(size)"
          @click="onResize(size.colSpan, size.rowSpan)"
        />
        <v-divider class="my-1" />
        <v-list-item
          prepend-icon="mdi-delete-outline"
          title="删除磁贴"
          base-color="error"
          :disabled="!!menuTargetItem?.fixed"
          @click="onDelete"
        >
          <template v-if="menuTargetItem?.fixed" #append>
            <v-tooltip location="left" text="系统磁贴，不可删除">
              <template #activator="{ props: tipProps }">
                <v-icon v-bind="tipProps" icon="mdi-lock-outline" size="14" />
              </template>
            </v-tooltip>
          </template>
        </v-list-item>
      </v-list>
    </v-menu>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import AgentTile from "./tiles/AgentTile.vue";
import SelectionTile from "./tiles/SelectionTile.vue";
import PlaceholderTile from "./tiles/PlaceholderTile.vue";
import TaskTile from "./tiles/TaskTile.vue";
import FileTile from "./tiles/FileTile.vue";
import CitationTile from "./tiles/CitationTile.vue";
import DashboardTile from "./tiles/DashboardTile.vue";
import QuizTile from "./tiles/QuizTile.vue";
import FlashcardTile from "./tiles/FlashcardTile.vue";

// ─── Types ───────────────────────────────────────────
export interface ActiveAgent {
  title: string;
  phase: string;
  worker?: string;
  progress: number;
}

export interface SelectedCard {
  title?: string;
  icon?: string;
  detail?: string;
}

export interface Citation {
  source: string;
  page?: number;
  chunk: string;
  score: number;
}

export interface GridTile {
  id: string;
  kind: "agent" | "selection" | "placeholder" | "task" | "file" | "citation" | "dashboard" | "quiz" | "flashcard" | "empty";
  colSpan: 1 | 2;
  rowSpan: 1 | 2;
  title?: string;
  subtitle?: string;
  icon?: string;
  iconColor?: string;
  fixed?: boolean;
  filePath?: string;
  citations?: Citation[];
  quizData?: any;
  flashcards?: any[];
}

// ─── Props & Emits ───────────────────────────────────
const props = withDefaults(
  defineProps<{
    agent?: ActiveAgent | null;
    card?: SelectedCard | null;
    task?: any;
    taskStarting?: boolean;
    initialGridCols?: number;
    initialTiles?: GridTile[];
  }>(),
  {
    agent: null,
    card: null,
    task: null,
    taskStarting: false,
    initialGridCols: 3,
    initialTiles: () => [],
  }
);

const emit = defineEmits<{
  (e: "dismissAgent"): void;
  (e: "clearCard"): void;
  (e: "startTask", instruction: string): void;
  (e: "resumeTask", content: string): void;
  (e: "interruptTask"): void;
  (e: "addTile", slotId: string): void;
  (e: "update:tiles", tiles: GridTile[]): void;
  (e: "update:gridCols", cols: number): void;
}>();

// ─── Default layout ──────────────────────────────────
function makeDefaultTiles(): GridTile[] {
  return [
    // 2×2 大磁贴：编排任务 / Agent
    {
      id: "agent",
      kind: "agent",
      colSpan: 2,
      rowSpan: 2,
      fixed: true,
    },
    // 1×1 小磁贴：笔记摘要
    {
      id: "place-1",
      kind: "placeholder",
      colSpan: 1,
      rowSpan: 1,
      title: "笔记摘要",
      subtitle: "AI 自动总结",
      icon: "mdi-text-box-outline",
      iconColor: "indigo",
    },
    // 1×1 小磁贴：灵感
    {
      id: "place-2",
      kind: "placeholder",
      colSpan: 1,
      rowSpan: 1,
      title: "灵感",
      subtitle: "随手记一笔",
      icon: "mdi-lightbulb-on-outline",
      iconColor: "amber",
    },
    // 1×2 竖磁贴：RAG 引用
    {
      id: "place-3",
      kind: "citation",
      colSpan: 1,
      rowSpan: 2,
      title: "RAG 引用",
      subtitle: "知识库检索结果",
      icon: "mdi-bookshelf",
      iconColor: "success",
    },
    // 1×1：文件
    {
      id: "place-4",
      kind: "file",
      colSpan: 1,
      rowSpan: 1,
      title: "课件文件",
      subtitle: "拖入查看",
      icon: "mdi-file-pdf-box",
      iconColor: "red",
    },
    // 1×1：联网搜索
    {
      id: "place-5",
      kind: "placeholder",
      colSpan: 1,
      rowSpan: 1,
      title: "联网搜索",
      subtitle: "Tavily 结果",
      icon: "mdi-web",
      iconColor: "blue",
    },
    // Selection 卡片（1×1 固定）
    {
      id: "selection",
      kind: "selection",
      colSpan: 1,
      rowSpan: 1,
      fixed: true,
    },
    // 1×1：测验
    {
      id: "place-6",
      kind: "placeholder",
      colSpan: 1,
      rowSpan: 1,
      title: "测验",
      subtitle: "AI 出题",
      icon: "mdi-help-circle-outline",
      iconColor: "pink",
    },
    // 末尾空格子："+" 添加
    {
      id: "add-slot",
      kind: "empty",
      colSpan: 1,
      rowSpan: 1,
      fixed: true,
    },
  ];
}

// ─── Layout toggle ──────────────────────────────────
const gridCols = ref(props.initialGridCols);
const layoutLabel = computed(() =>
  gridCols.value === 2 ? "2×2 布局" : "3×3 布局"
);

function onToggleCols(n: number) {
  if (n === gridCols.value) return;
  gridCols.value = n;
  emit("update:gridCols", n);
}

// ─── Tiles state ────────────────────────────────────
const tiles = ref<GridTile[]>(
  props.initialTiles.length > 0 ? [...props.initialTiles] : makeDefaultTiles()
);

// 合入 props.initialTiles 变化
watch(
  () => props.initialTiles,
  (val) => {
    if (val && val.length > 0) {
      tiles.value = [...val];
    }
  },
  { deep: true }
);

// 布局变化 → 通知父组件持久化
watch(
  tiles,
  () => {
    emit("update:tiles", [...tiles.value]);
  },
  { deep: true }
);
watch(
  gridCols,
  () => {
    emit("update:gridCols", gridCols.value);
  },
  { immediate: true }
);

// ─── Helpers ────────────────────────────────────────
const sizeLabel = (tile: { colSpan: number; rowSpan: number }) =>
  `${tile.colSpan}×${tile.rowSpan}` as "1x1" | "1x2" | "2x2";

const SIZE_OPTIONS = [
  { key: "1x1", label: "小 · 1×1", icon: "mdi-square-outline", colSpan: 1, rowSpan: 1 },
  { key: "1x2", label: "高 · 1×2", icon: "mdi-arrow-expand-vertical", colSpan: 1, rowSpan: 2 },
  { key: "2x2", label: "大 · 2×2", icon: "mdi-crop-square", colSpan: 2, rowSpan: 2 },
] as const;

// ─── Context menu ───────────────────────────────────
const menuOpen = ref(false);
const menuTarget = ref<[number, number]>([0, 0]);
const menuTargetItem = ref<GridTile | null>(null);

const onContextMenu = (e: MouseEvent, tile: GridTile) => {
  if (tile.kind === "empty") return; // 空格子无右键菜单
  menuOpen.value = false;
  menuTargetItem.value = tile;
  menuTarget.value = [e.clientX, e.clientY];
  requestAnimationFrame(() => {
    menuOpen.value = true;
  });
};

const isCurrentSize = (size: { colSpan: number; rowSpan: number }) => {
  const t = menuTargetItem.value;
  return !!t && t.colSpan === size.colSpan && t.rowSpan === size.rowSpan;
};

const onResize = (colSpan: 1 | 2, rowSpan: 1 | 2) => {
  const t = menuTargetItem.value;
  if (!t) return;
  const idx = tiles.value.findIndex((x) => x.id === t.id);
  if (idx === -1) return;
  tiles.value[idx] = { ...tiles.value[idx], colSpan, rowSpan };
  menuOpen.value = false;
};

const onDelete = () => {
  const t = menuTargetItem.value;
  if (!t || t.fixed) return;
  tiles.value = tiles.value.filter((x) => x.id !== t.id);
  menuOpen.value = false;
};
</script>

<style scoped lang="scss">
.tile-grid-root {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tile-grid-toolbar {
  flex-shrink: 0;
  padding: 2px 2px 6px;
}

.tile-grid-css {
  flex: 1 1 auto;
  display: grid;
  gap: 8px;
  align-content: start;
  overflow-y: auto;
  padding: 0 2px 16px;
}

.tile-cell {
  min-height: 110px;
  display: flex;
  flex-direction: column;

  &.tile-empty {
    min-height: 90px;
    border: 2px dashed rgba(128, 128, 128, 0.35);
    border-radius: 10px;
    transition:
      border-color 0.18s,
      background 0.18s;

    &:hover {
      border-color: rgba(33, 150, 243, 0.45);
      background: rgba(33, 150, 243, 0.06);
    }
  }
}

.empty-slot {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  cursor: pointer;
  border-radius: 10px;
  user-select: none;
}
</style>
