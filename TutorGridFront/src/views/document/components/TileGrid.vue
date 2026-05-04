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
        class="layout-toggle"
        :model-value="gridCols"
        mandatory
        density="compact"
        variant="outlined"
        divided
        @update:model-value="onToggleCols"
      >
        <v-btn :value="2" size="x-small" min-width="52">2 列</v-btn>
        <v-btn :value="3" size="x-small" min-width="52">3 列</v-btn>
      </v-btn-toggle>
    </div>

    <!-- CSS Grid 容器 -->
    <div
      class="tile-grid-css"
      :style="gridStyle"
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
        <div v-else class="empty-slot" @click="(e) => onAddSlotClick(e, tile)">
          <v-icon icon="mdi-plus-circle-outline" size="28" color="grey-lighten-1" />
          <span class="text-caption text-grey">添加磁贴</span>
        </div>
      </div>
    </div>

    <!-- 添加磁贴菜单 -->
    <v-menu
      v-model="addMenuOpen"
      :target="addMenuTarget"
      :close-on-content-click="true"
      location="start"
    >
      <v-list density="compact" min-width="220" rounded="lg">
        <v-list-subheader class="text-caption">添加磁贴</v-list-subheader>
        <v-list-item
          v-for="option in ADD_TILE_OPTIONS"
          :key="option.kind"
          :prepend-icon="option.icon"
          :title="option.label"
          :subtitle="option.description"
          @click="addTile(option.kind)"
        />
      </v-list>
    </v-menu>

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
import type { ChatCitation } from "@/lib/chat-sse";

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
    autoCitations?: ChatCitation[];
    autoArtifacts?: Array<Record<string, unknown>>;
    initialGridCols?: number;
    initialTiles?: GridTile[];
  }>(),
  {
    agent: null,
    card: null,
    task: null,
    taskStarting: false,
    autoCitations: () => [],
    autoArtifacts: () => [],
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
  (e: "update:tiles", tiles: GridTile[]): void;
  (e: "update:gridCols", cols: number): void;
}>();

// ─── Default layout ──────────────────────────────────
function makeDefaultTiles(): GridTile[] {
  return [
    // 2×2 大磁贴：编排任务（F12 主入口）
    {
      id: "task",
      kind: "task",
      colSpan: 2,
      rowSpan: 2,
      fixed: true,
    },
    // 1×2 竖磁贴：RAG 引用（F09 CitationTile 展示示例数据）
    {
      id: "place-3",
      kind: "citation",
      colSpan: 1,
      rowSpan: 2,
      title: "知识库引用",
      citations: [
        { source: "数据挖掘PPT_第3章", page: 42, chunk: "线性回归的核心思想是通过最小化均方误差（MSE）来拟合一条直线…", score: 0.92 },
        { source: "机器学习_周志华", page: 53, chunk: "线性模型试图学得一个通过属性的线性组合来进行预测的函数…", score: 0.85 },
      ],
      fixed: false,
    },
    // 1×1：活跃 Agent 状态
    {
      id: "agent",
      kind: "agent",
      colSpan: 1,
      rowSpan: 1,
      fixed: true,
    },
    // 1×1 小磁贴：文件预览（F09 FileTile）
    {
      id: "place-4",
      kind: "file",
      colSpan: 1,
      rowSpan: 1,
      title: "数据挖掘导论.pdf",
      subtitle: "2.3 MB",
      icon: "mdi-file-pdf-box",
      iconColor: "red",
    },
    // 1×1：测验（F14 QuizTile 展示示例）
    {
      id: "place-6",
      kind: "quiz",
      colSpan: 1,
      rowSpan: 1,
      title: "快问快答",
      quizData: {
        question: "线性回归常用的损失函数是？",
        options: ["交叉熵", "均方误差 MSE", "Hinge Loss", "KL 散度"],
        answer: 1,
        explanation: "线性回归通常使用均方误差（MSE）作为损失函数，衡量预测值与真实值之差的平方和。",
      },
    },
    // 1×1：闪卡（F14 FlashcardTile 展示示例）
    {
      id: "place-2",
      kind: "flashcard",
      colSpan: 1,
      rowSpan: 1,
      title: "知识点闪卡",
      flashcards: [
        { front: "什么是过拟合？", back: "模型在训练集上表现很好，但在测试集上表现差，泛化能力弱。" },
        { front: "L1 与 L2 正则化的区别？", back: "L1 产生稀疏解（特征选择），L2 使权重趋近于零但不为零。" },
      ],
    },
    // 1×1：仪表板状态（F15 DashboardTile）
    {
      id: "place-5",
      kind: "dashboard",
      colSpan: 1,
      rowSpan: 1,
    },
    // Selection 卡片（1×1 固定）
    {
      id: "selection",
      kind: "selection",
      colSpan: 1,
      rowSpan: 1,
      fixed: true,
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
  gridCols.value === 2 ? "2 列磁贴" : "3 列磁贴"
);
const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${gridCols.value}, minmax(0, 1fr))`,
  gridAutoRows: gridCols.value === 2 ? "minmax(184px, 1fr)" : "minmax(156px, 1fr)",
}));

function onToggleCols(n: number) {
  if (n === gridCols.value) return;
  gridCols.value = n;
  emit("update:gridCols", n);
}

// ─── Tiles state ────────────────────────────────────
const tiles = ref<GridTile[]>(
  normalizeTiles(props.initialTiles.length > 0 ? [...props.initialTiles] : makeDefaultTiles())
);

function normalizeTiles(input: GridTile[]): GridTile[] {
  const next = input.map((tile) => ({ ...tile }));
  const hasTaskTile = next.some((tile) => tile.kind === "task");
  if (!hasTaskTile) {
    const oldLargeAgent = next.find((tile) => tile.kind === "agent" && tile.colSpan === 2 && tile.rowSpan === 2);
    if (oldLargeAgent) {
      oldLargeAgent.colSpan = 1;
      oldLargeAgent.rowSpan = 1;
    }
    next.unshift({
      id: "task",
      kind: "task",
      colSpan: 2,
      rowSpan: 2,
      fixed: true,
    });
  }
  return next;
}

// 合入 props.initialTiles 变化
watch(
  () => props.initialTiles,
  (val) => {
    if (val && val.length > 0) {
      tiles.value = normalizeTiles([...val]);
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
  `${tile.colSpan}x${tile.rowSpan}` as "1x1" | "1x2" | "2x2";

const SIZE_OPTIONS = [
  { key: "1x1", label: "小 · 1×1", icon: "mdi-square-outline", colSpan: 1, rowSpan: 1 },
  { key: "1x2", label: "高 · 1×2", icon: "mdi-arrow-expand-vertical", colSpan: 1, rowSpan: 2 },
  { key: "2x2", label: "大 · 2×2", icon: "mdi-crop-square", colSpan: 2, rowSpan: 2 },
] as const;

const AUTO_CITATION_TILE_ID = "auto-citation";
const AUTO_ARTIFACT_PREFIX = "auto-artifact-";

function simpleHash(value: string) {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  }
  return hash.toString(36);
}

function citationFromAi(citation: ChatCitation): Citation | null {
  const chunk = String(citation.chunk || citation.content || "").trim();
  const source = String(citation.source || citation.fileName || citation.fileId || "AI 引用").trim();
  if (!chunk && !source) return null;
  const rawScore = Number(citation.score ?? 0);
  const rawPage = Number(citation.page);
  return {
    source,
    page: Number.isFinite(rawPage) && rawPage > 0 ? rawPage : undefined,
    chunk: chunk || "AI 返回了引用来源，但未提供片段正文。",
    score: Number.isFinite(rawScore) && rawScore > 0 ? rawScore : 0.75,
  };
}

function upsertGeneratedTile(tile: GridTile, replaceKind?: GridTile["kind"]) {
  const existingIndex = tiles.value.findIndex((item) => item.id === tile.id);
  if (existingIndex >= 0) {
    tiles.value[existingIndex] = { ...tiles.value[existingIndex], ...tile };
    return;
  }

  const replaceIndex = replaceKind
    ? tiles.value.findIndex((item) => item.kind === replaceKind && !item.fixed)
    : -1;
  if (replaceIndex >= 0) {
    tiles.value[replaceIndex] = tile;
    return;
  }

  const emptyIndex = tiles.value.findIndex((item) => item.kind === "empty");
  if (emptyIndex >= 0) {
    tiles.value.splice(emptyIndex, 0, tile);
  } else {
    tiles.value.push(tile);
  }
  ensureEmptySlot();
}

function syncAutoCitations(rawCitations: ChatCitation[]) {
  const citations = rawCitations
    .map(citationFromAi)
    .filter((citation): citation is Citation => !!citation)
    .slice(-6);
  if (!citations.length) return;

  upsertGeneratedTile(
    {
      id: AUTO_CITATION_TILE_ID,
      kind: "citation",
      colSpan: 1,
      rowSpan: 2,
      title: "RAG 引用",
      citations,
    },
    "citation"
  );
}

function artifactText(artifact: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = artifact[key];
    if (typeof value === "string" && value.trim()) return value.trim();
    if (typeof value === "number" && Number.isFinite(value)) return String(value);
  }
  return "";
}

function fileNameFromPath(path: string) {
  return path.split(/[\\/]/).filter(Boolean).pop() || path;
}

function tileFromArtifact(artifact: Record<string, unknown>, index: number): GridTile | null {
  const path = artifactText(artifact, ["path", "file_path", "relPath", "rel_path", "url"]);
  const title = artifactText(artifact, ["title", "name", "filename", "fileName"]) || fileNameFromPath(path);
  if (!title) return null;
  const type = artifactText(artifact, ["type", "kind", "mime", "mimeType"]);
  const summary = artifactText(artifact, ["summary", "description", "content"]);
  const subtitle = [type, summary || path].filter(Boolean).join(" · ");
  const idBase = path || title || String(index);

  return {
    id: `${AUTO_ARTIFACT_PREFIX}${simpleHash(idBase)}`,
    kind: "file",
    colSpan: 1,
    rowSpan: 1,
    title,
    subtitle: subtitle || "任务产物",
    filePath: path || undefined,
  };
}

function syncAutoArtifacts(rawArtifacts: Array<Record<string, unknown>>) {
  const artifactTiles = rawArtifacts
    .map(tileFromArtifact)
    .filter((tile): tile is GridTile => !!tile)
    .slice(-3);
  if (!artifactTiles.length) return;

  const nextIds = new Set(artifactTiles.map((tile) => tile.id));
  tiles.value = tiles.value.filter(
    (tile) => !tile.id.startsWith(AUTO_ARTIFACT_PREFIX) || nextIds.has(tile.id)
  );
  artifactTiles.forEach((tile, index) => {
    upsertGeneratedTile(tile, index === 0 ? "file" : undefined);
  });
}

watch(
  () => props.autoCitations,
  (val) => {
    syncAutoCitations(val ?? []);
  },
  { deep: true, immediate: true }
);

watch(
  () => props.autoArtifacts,
  (val) => {
    syncAutoArtifacts(val ?? []);
  },
  { deep: true, immediate: true }
);

// ─── Context menu ───────────────────────────────────
const menuOpen = ref(false);
const menuTarget = ref<[number, number]>([0, 0]);
const menuTargetItem = ref<GridTile | null>(null);
const addMenuOpen = ref(false);
const addMenuTarget = ref<[number, number]>([0, 0]);
const addTargetId = ref("");

const ADD_TILE_OPTIONS = [
  {
    kind: "task",
    label: "编排任务",
    description: "注册多步执行任务",
    icon: "mdi-cog-sync-outline",
  },
  {
    kind: "citation",
    label: "RAG 引用",
    description: "展示课程资料引用",
    icon: "mdi-bookshelf",
  },
  {
    kind: "file",
    label: "文件预览",
    description: "展示课程文件或产物",
    icon: "mdi-file-outline",
  },
  {
    kind: "quiz",
    label: "测验题",
    description: "选择题与批改反馈",
    icon: "mdi-help-circle-outline",
  },
  {
    kind: "flashcard",
    label: "闪卡",
    description: "知识点正反面记忆卡",
    icon: "mdi-card-bulleted-outline",
  },
  {
    kind: "dashboard",
    label: "工作区概览",
    description: "知识库和学习进度",
    icon: "mdi-view-dashboard-outline",
  },
  {
    kind: "agent",
    label: "活跃 Agent",
    description: "显示当前执行状态",
    icon: "mdi-flash-outline",
  },
] as const;

type AddTileKind = (typeof ADD_TILE_OPTIONS)[number]["kind"];

const onContextMenu = (e: MouseEvent, tile: GridTile) => {
  if (tile.kind === "empty") return; // 空格子无右键菜单
  menuOpen.value = false;
  menuTargetItem.value = tile;
  menuTarget.value = [e.clientX, e.clientY];
  requestAnimationFrame(() => {
    menuOpen.value = true;
  });
};

const onAddSlotClick = (e: MouseEvent, tile: GridTile) => {
  addTargetId.value = tile.id;
  addMenuOpen.value = false;
  addMenuTarget.value = [e.clientX, e.clientY];
  requestAnimationFrame(() => {
    addMenuOpen.value = true;
  });
};

function createTile(kind: AddTileKind): GridTile {
  const id = `${kind}-${Date.now()}`;
  if (kind === "task") {
    return {
      id,
      kind: "task",
      colSpan: 2,
      rowSpan: 2,
      title: "编排任务",
    };
  }
  if (kind === "citation") {
    return {
      id,
      kind: "citation",
      colSpan: 1,
      rowSpan: 2,
      title: "RAG 引用",
      citations: [
        {
          source: "课程资料",
          page: 12,
          chunk: "这里会展示 RAG 检索到的课程原文片段和相关度。",
          score: 0.78,
        },
      ],
    };
  }
  if (kind === "file") {
    return {
      id,
      kind: "file",
      colSpan: 1,
      rowSpan: 1,
      title: "新文件.pdf",
      subtitle: "点击预览",
      icon: "mdi-file-pdf-box",
      iconColor: "red",
    };
  }
  if (kind === "quiz") {
    return {
      id,
      kind: "quiz",
      colSpan: 1,
      rowSpan: 1,
      title: "测验题",
      quizData: {
        question: "线性回归常用的损失函数是？",
        options: ["交叉熵", "均方误差 MSE", "Hinge Loss", "KL 散度"],
        answer: 1,
        explanation: "线性回归通常使用均方误差（MSE）作为损失函数。",
      },
    };
  }
  if (kind === "flashcard") {
    return {
      id,
      kind: "flashcard",
      colSpan: 1,
      rowSpan: 1,
      title: "闪卡",
      flashcards: [
        {
          front: "什么是过拟合？",
          back: "模型在训练集表现好，但测试集表现差，泛化能力弱。",
        },
      ],
    };
  }
  if (kind === "dashboard") {
    return {
      id,
      kind: "dashboard",
      colSpan: 1,
      rowSpan: 1,
      title: "工作区概览",
    };
  }
  return {
    id,
    kind: "agent",
    colSpan: 1,
    rowSpan: 1,
    title: "活跃 Agent",
  };
}

function ensureEmptySlot() {
  if (tiles.value.some((tile) => tile.kind === "empty")) return;
  tiles.value.push({
    id: `add-${Date.now()}`,
    kind: "empty",
    colSpan: 1,
    rowSpan: 1,
    fixed: true,
  });
}

const addTile = (kind: AddTileKind) => {
  const targetId = addTargetId.value;
  const idx = tiles.value.findIndex((tile) => tile.id === targetId);
  const nextTile = createTile(kind);
  if (idx >= 0) {
    tiles.value.splice(idx, 1, nextTile);
  } else {
    tiles.value.push(nextTile);
  }
  ensureEmptySlot();
  addMenuOpen.value = false;
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
  ensureEmptySlot();
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
  min-height: 34px;
}

.layout-toggle {
  flex-shrink: 0;
}

.tile-grid-css {
  flex: 1 1 auto;
  display: grid;
  gap: 8px;
  align-content: start;
  overflow-y: auto;
  padding: 0 2px 16px;
  min-height: 0;
}

.tile-cell {
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  &.tile-empty {
    min-height: 0;
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
