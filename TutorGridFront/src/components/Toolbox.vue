<!--
* @Component: BackToTop
* @Maintainer: J.K. Yang
* @Description:
-->
<script setup lang="ts">
import { Icon } from "@iconify/vue";
import { computed } from "vue";
import ChatAssistant from "@/components/ai/ChatAssistant.vue";
import { useOrchestratorTaskStore } from "@/stores/orchestratorTaskStore";

const toolboxShow = ref(false);
const taskStore = useOrchestratorTaskStore();

// 编排 drawer 全局入口：哪怕没在文档里选中触发,也能从这里随时调出
const taskCount = computed(() => Object.keys(taskStore.tasksById).length);
const runningCount = computed(() =>
  Object.values(taskStore.tasksById).filter(
    (t) => t.status === "running" || t.status === "awaiting_user"
  ).length
);

function openOrchestration() {
  // 优先打开正在跑的；否则打开最近一个；都没有就把 drawer 直接打开（空态）
  const running = Object.values(taskStore.tasksById).find(
    (t) => t.status === "running" || t.status === "awaiting_user"
  );
  if (running) {
    taskStore.openDrawer(running.taskId);
    return;
  }
  const recent = Object.values(taskStore.tasksById).sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
  )[0];
  if (recent) {
    taskStore.openDrawer(recent.taskId);
    return;
  }
  // 无任务时,只把 drawer 标记为开;drawer 内部对 task=null 有空态展示
  taskStore.drawerOpen = true;
}
</script>

<template>
  
  <v-btn
    class="toolbox-activator elevation-10"
    @click="toolboxShow = !toolboxShow"
    size="50"
    color="white"
  >
    <Icon width="30" icon="ri:openai-fill" />
  </v-btn>

  <transition name="slide-y">
    <v-card
      v-if="toolboxShow"
      elevation="10"
      class="d-flex flex-column mb-1 toolbox"
    >
      <!-- Chat Assistant -->
      <ChatAssistant />
      <v-divider />
      <!-- 后续可加 Translation / Voice / 其它工具 -->
       <!-- 编排 drawer 入口(在 OpenAI 圆按钮上方) -->
      <!-- 编排 drawer 入口（已修复样式） -->
      <!-- 使用 variant="text" 或 icon 让它融入 v-card 的组内 -->
      <v-btn
        icon
        variant="text"
        @click="openOrchestration"
        size="48" 
        :title="`打开编排 (${runningCount}/${taskCount})`"
      >
        <v-badge
          v-if="runningCount > 0"
          color="primary"
          :content="runningCount"
          floating
          offset-x="2"
          offset-y="2"
        >
          <Icon width="24" icon="mdi:cog-sync-outline" />
        </v-badge>
        
        <!-- 如果没有 runningCount，只显示 Icon -->
        <Icon v-else width="24" icon="mdi:cog-sync-outline" />
      </v-btn>

    </v-card>
  </transition>
</template>

<style scoped lang="scss">
.toolbox {
  z-index: 999;
  position: fixed;
  bottom: 150px;
  right: 5px;
}

.toolbox-activator {
  position: fixed;
  transition: all 0.3s ease;
  bottom: 100px;
  right: 5px;
  z-index: 999;
  padding: 0.5rem;
  border-radius: 0.5rem;
  transition: all 0.3s;
  cursor: pointer;
}

.orchestration-activator {
  position: fixed;
  transition: all 0.3s ease;
  bottom: 50px;
  right: 8px;
  z-index: 999;
  padding: 0.4rem;
  border-radius: 0.5rem;
  cursor: pointer;
}
</style>
