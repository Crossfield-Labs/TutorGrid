<!--
  Hyper 文档右栏磁贴网格 (F06 占位骨架)
  - 4 列 Win10 风格磁贴
  - 尺寸固定 {1×1, 1×2, 2×2}
  - 拖拽推挤（grid-layout-plus 原生支持）
  - F08 由前端B 接手：增删改、持久化、布局切换
-->
<template>
  <div ref="containerRef" class="tile-grid">
    <GridLayout
      v-model:layout="internalLayout"
      :col-num="COL_NUM"
      :row-height="dynamicRowHeight"
      :margin="MARGIN"
      :is-draggable="true"
      :is-resizable="false"
      :vertical-compact="true"
      :use-css-transforms="true"
      drag-allow-from=".tile-handle"
    >
      <GridItem
        v-for="item in internalLayout"
        :key="item.i"
        :x="item.x"
        :y="item.y"
        :w="item.w"
        :h="item.h"
        :i="item.i"
        :min-w="1"
        :max-w="2"
        :min-h="1"
        :max-h="2"
        class="tile-handle"
      >
        <!-- AgentTile -->
        <AgentTile
          v-if="item.kind === 'agent'"
          :agent="agent"
          @dismiss="$emit('dismissAgent')"
        />

        <!-- SelectionTile -->
        <SelectionTile
          v-else-if="item.kind === 'selection'"
          :card="card"
          @clear="$emit('clearCard')"
        />

        <!-- 占位磁贴（F08 替换） -->
        <PlaceholderTile
          v-else
          :title="item.title || '占位'"
          :subtitle="item.subtitle"
          :icon="item.icon"
          :icon-color="item.iconColor"
          :size="sizeLabel(item)"
        />
      </GridItem>
    </GridLayout>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useResizeObserver } from "@vueuse/core";
import { GridLayout, GridItem } from "grid-layout-plus";
import AgentTile from "./tiles/AgentTile.vue";
import SelectionTile from "./tiles/SelectionTile.vue";
import PlaceholderTile from "./tiles/PlaceholderTile.vue";

// ⚙️ 微调点 ① ：列数 / 间隙
//   COL_NUM   网格列数 (默认 4)
//   MARGIN   [水平间隙, 垂直间隙] 单位 px
const COL_NUM = 4;
const MARGIN: [number, number] = [6, 6];

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

interface TileLayoutItem {
  i: string;
  x: number;
  y: number;
  w: 1 | 2;
  h: 1 | 2;
  kind: "agent" | "selection" | "placeholder";
  title?: string;
  subtitle?: string;
  icon?: string;
  iconColor?: string;
}

withDefaults(
  defineProps<{
    agent?: ActiveAgent | null;
    card?: SelectedCard | null;
  }>(),
  {
    agent: null,
    card: null,
  }
);

// 容器宽度 → 动态 rowHeight，保证 1×1 始终是正方形
//   每列宽度 = (容器宽 - (列数+1)*水平间隙) / 列数
//   rowHeight = 每列宽度
const containerRef = ref<HTMLElement | null>(null);
const containerWidth = ref(0);

useResizeObserver(containerRef, (entries) => {
  containerWidth.value = entries[0].contentRect.width;
});

const dynamicRowHeight = computed(() => {
  const w = containerWidth.value;
  if (!w) return 130; // 首屏 fallback
  const colWidth = (w - (COL_NUM + 1) * MARGIN[0]) / COL_NUM;
  return Math.max(80, Math.floor(colWidth));
});

defineEmits<{
  (e: "dismissAgent"): void;
  (e: "clearCard"): void;
}>();

// F06 默认布局：演示 1×1 / 1×2 / 2×2 三种尺寸
const defaultLayout: TileLayoutItem[] = [
  {
    i: "agent",
    x: 0,
    y: 0,
    w: 2,
    h: 2,
    kind: "agent",
  },
  {
    i: "place-1",
    x: 2,
    y: 0,
    w: 1,
    h: 1,
    kind: "placeholder",
    title: "笔记摘要",
    subtitle: "AI 自动总结当前段落",
    icon: "mdi-text-box-outline",
    iconColor: "indigo",
  },
  {
    i: "place-2",
    x: 3,
    y: 0,
    w: 1,
    h: 1,
    kind: "placeholder",
    title: "灵感",
    subtitle: "随手记一笔",
    icon: "mdi-lightbulb-on-outline",
    iconColor: "amber",
  },
  {
    i: "place-3",
    x: 2,
    y: 1,
    w: 1,
    h: 2,
    kind: "placeholder",
    title: "RAG 引用",
    subtitle: "知识库检索结果会在这里堆叠展示",
    icon: "mdi-bookshelf",
    iconColor: "success",
  },
  {
    i: "place-4",
    x: 3,
    y: 1,
    w: 1,
    h: 2,
    kind: "placeholder",
    title: "联网搜索",
    subtitle: "Tavily 抓回的最新资料",
    icon: "mdi-web",
    iconColor: "blue",
  },
  {
    i: "place-5",
    x: 0,
    y: 2,
    w: 2,
    h: 2,
    kind: "placeholder",
    title: "编排任务",
    subtitle: "/task 触发的多步任务进度",
    icon: "mdi-cog-sync-outline",
    iconColor: "deep-purple",
  },
  {
    i: "selection",
    x: 2,
    y: 3,
    w: 1,
    h: 1,
    kind: "selection",
  },
  {
    i: "place-6",
    x: 3,
    y: 3,
    w: 1,
    h: 1,
    kind: "placeholder",
    title: "测验",
    subtitle: "AI 出题",
    icon: "mdi-help-circle-outline",
    iconColor: "pink",
  },
];

const internalLayout = ref<TileLayoutItem[]>([...defaultLayout]);

// F06 暂不持久化（按确认 #4），F08 接 tile.metadata
watch(
  internalLayout,
  () => {
    // placeholder for future persistence
  },
  { deep: true }
);

const sizeLabel = (item: { w: number; h: number }) =>
  `${item.w}×${item.h}` as "1x1" | "1x2" | "2x2";
</script>

<style scoped lang="scss">
.tile-grid {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0px 4px 16px;

  // grid-layout-plus 容器需要相对定位
  :deep(.vgl-layout) {
    min-height: 100%;
  }

  // 拖拽时占位虚影
  :deep(.vgl-item--placeholder) {
    background: rgba(33, 150, 243, 0.18);
    border: 1.5px dashed rgba(33, 150, 243, 0.5);
    border-radius: 10px;
    opacity: 1;
  }

  // 拖拽中的磁贴
  :deep(.vgl-item--dragging) {
    cursor: grabbing;
    opacity: 0.85;
    z-index: 100;
  }

  :deep(.vgl-item) {
    cursor: grab;
  }

  :deep(.vgl-item--dragging),
  :deep(.vgl-item--resizing) {
    cursor: grabbing;
  }
}
</style>
