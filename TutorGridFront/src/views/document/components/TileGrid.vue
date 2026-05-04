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
        <div
          class="tile-slot"
          @contextmenu.prevent="(e) => onContextMenu(e, item)"
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

          <TaskTile
            v-else-if="item.kind === 'task'"
            :task="task"
            :starting="taskStarting"
            :size="sizeLabel(item)"
            @start="(instruction) => emit('startTask', instruction)"
            @resume="(content) => emit('resumeTask', content)"
            @interrupt="emit('interruptTask')"
          />

          <!-- 编排 plan step 磁贴（按 declare_plan 动态生成）-->
          <StepTile
            v-else-if="item.kind === 'step' && resolveStep(item)"
            :step="resolveStep(item)!"
            :task-id="item.taskId || ''"
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
        </div>
      </GridItem>
    </GridLayout>

    <!-- 右键菜单（共享一个） -->
    <v-menu
      v-model="menuOpen"
      :target="menuTarget"
      :close-on-content-click="true"
      location="end"
    >
      <v-list density="compact" min-width="180" rounded="lg">
        <v-list-subheader class="text-caption">调整大小</v-list-subheader>
        <v-list-item
          v-for="size in SIZE_OPTIONS"
          :key="size.key"
          :prepend-icon="size.icon"
          :title="size.label"
          :disabled="isCurrentSize(size)"
          @click="onResize(size.w, size.h)"
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
            <v-tooltip
              location="left"
              text="系统磁贴，不可删除"
            >
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
import { useResizeObserver } from "@vueuse/core";
import { GridLayout, GridItem } from "grid-layout-plus";
import AgentTile from "./tiles/AgentTile.vue";
import SelectionTile from "./tiles/SelectionTile.vue";
import PlaceholderTile from "./tiles/PlaceholderTile.vue";
import TaskTile from "./tiles/TaskTile.vue";
import StepTile from "./tiles/StepTile.vue";
import { useOrchestratorTaskStore } from "@/stores/orchestratorTaskStore";

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
  kind: "agent" | "selection" | "placeholder" | "task" | "step";
  title?: string;
  subtitle?: string;
  icon?: string;
  iconColor?: string;
  fixed?: boolean;          // true = 系统磁贴，不可删除（仍可调大小）
  /** for kind='step': which task & which plan step.id this tile renders */
  taskId?: string;
  stepId?: string;
}

// 右键菜单可选尺寸（任务书定义：1×1 / 1×2 / 2×2）
const SIZE_OPTIONS: { key: string; label: string; icon: string; w: 1 | 2; h: 1 | 2 }[] = [
  { key: "1x1", label: "小 · 1×1", icon: "mdi-square-outline", w: 1, h: 1 },
  { key: "1x2", label: "竖 · 1×2", icon: "mdi-rectangle-outline", w: 1, h: 2 },
  { key: "2x2", label: "大 · 2×2", icon: "mdi-checkbox-blank-outline", w: 2, h: 2 },
];

const props = withDefaults(
  defineProps<{
    agent?: ActiveAgent | null;
    card?: SelectedCard | null;
    task?: any;
    taskStarting?: boolean;
  }>(),
  {
    agent: null,
    card: null,
    task: null,
    taskStarting: false,
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

const emit = defineEmits<{
  (e: "dismissAgent"): void;
  (e: "clearCard"): void;
  (e: "startTask", instruction: string): void;
  (e: "resumeTask", content: string): void;
  (e: "interruptTask"): void;
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
    fixed: true,
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
    kind: "task",
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
    fixed: true,
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

// ─────────────────────────────────────────────────────────
// Plan-step 磁贴动态注入：监听 props.task.plan，把 N 个 plan step
// 投影成 N 个 1×1 'step' kind 磁贴，追加到 layout 末尾。
// 同 plan 重新声明时按 step.id 同步（已存在的就地更新，不重排）。
// 切到无 plan 任务（或任务无 plan）时清掉所有 step 磁贴。
// ─────────────────────────────────────────────────────────
const taskStore = useOrchestratorTaskStore();
const planSteps = computed(() => {
  const t = props.task as { taskId?: string; plan?: { steps?: Array<{ id: string }> } } | null;
  if (!t?.taskId) return [];
  return taskStore.planStepsForTask(t.taskId);
});

function resolveStep(item: TileLayoutItem) {
  if (!item.taskId || !item.stepId) return null;
  return taskStore.planStepsForTask(item.taskId).find((s) => s.id === item.stepId) || null;
}

function nextFreeSlot(layout: TileLayoutItem[]): { x: number; y: number } {
  // simple bottom-left scan: find lowest y with a free 1×1 slot
  const occupied = new Set<string>();
  for (const item of layout) {
    for (let dx = 0; dx < item.w; dx++) {
      for (let dy = 0; dy < item.h; dy++) {
        occupied.add(`${item.x + dx},${item.y + dy}`);
      }
    }
  }
  for (let y = 0; y < 100; y++) {
    for (let x = 0; x < COL_NUM; x++) {
      if (!occupied.has(`${x},${y}`)) return { x, y };
    }
  }
  return { x: 0, y: 100 };
}

watch(
  planSteps,
  (steps) => {
    const t = props.task as { taskId?: string } | null;
    const taskId = t?.taskId || "";
    // 1. drop step tiles that no longer belong to the current plan
    const wantedIds = new Set(steps.map((s) => `step-tile:${taskId}:${s.id}`));
    internalLayout.value = internalLayout.value.filter((item) => {
      if (item.kind !== "step") return true;
      // keep only step tiles for the current task that exist in current plan
      if (item.taskId !== taskId) return false;
      return wantedIds.has(item.i);
    });
    // 2. append any missing step tile to the next free slot
    for (const step of steps) {
      const id = `step-tile:${taskId}:${step.id}`;
      if (internalLayout.value.find((it) => it.i === id)) continue;
      const slot = nextFreeSlot(internalLayout.value);
      internalLayout.value.push({
        i: id,
        x: slot.x,
        y: slot.y,
        w: 1,
        h: 1,
        kind: "step",
        fixed: true,                    // 不可右键删除（任务还在跑/历史记录）
        taskId,
        stepId: step.id,
      });
    }
  },
  { deep: true, immediate: true },
);

const sizeLabel = (item: { w: number; h: number }) =>
  `${item.w}×${item.h}` as "1x1" | "1x2" | "2x2";

// ─────────────────────────────────────────────────────────
// 右键菜单
// ─────────────────────────────────────────────────────────
const menuOpen = ref(false);
const menuTarget = ref<[number, number]>([0, 0]);
const menuTargetItem = ref<TileLayoutItem | null>(null);

const onContextMenu = (e: MouseEvent, item: TileLayoutItem) => {
  // 先关再开，强制 v-menu 重新定位（防止连续右键不同磁贴时位置黏住）
  menuOpen.value = false;
  menuTargetItem.value = item;
  menuTarget.value = [e.clientX, e.clientY];
  // 下一帧再开，确保 target 已更新
  requestAnimationFrame(() => {
    menuOpen.value = true;
  });
};

const isCurrentSize = (size: { w: 1 | 2; h: 1 | 2 }) => {
  const t = menuTargetItem.value;
  return !!t && t.w === size.w && t.h === size.h;
};

const onResize = (w: 1 | 2, h: 1 | 2) => {
  const t = menuTargetItem.value;
  if (!t) return;
  // 直接改 layout 数组里的引用，grid-layout-plus 会重新排布并自动推挤碰撞磁贴
  const idx = internalLayout.value.findIndex((x) => x.i === t.i);
  if (idx === -1) return;
  internalLayout.value[idx] = { ...internalLayout.value[idx], w, h };
  menuOpen.value = false;
};

const onDelete = () => {
  const t = menuTargetItem.value;
  if (!t || t.fixed) return;
  internalLayout.value = internalLayout.value.filter((x) => x.i !== t.i);
  menuOpen.value = false;
};
</script>

<style scoped lang="scss">
.tile-grid {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0px 4px 16px;

  // 包裹磁贴内容，承接 contextmenu 事件
  .tile-slot {
    width: 100%;
    height: 100%;
  }

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
