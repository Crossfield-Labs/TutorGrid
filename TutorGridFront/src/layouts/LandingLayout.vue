<script setup lang="ts">
import { computed } from "vue";
import MainSidebar from "@/components/navigation/MainSidebar.vue";
import MainAppbar from "@/components/toolbar/MainAppbar.vue";
// import GlobalLoading from "@/components/GlobalLoading.vue";
import ToolBox from "@/components/Toolbox.vue";
import { useCustomizeThemeStore } from "@/stores/customizeTheme";
import { useProjectStore } from "@/stores/projectStore";
import { useWorkspaceAsset } from "@/composables/useWorkspaceAsset";

const customizeTheme = useCustomizeThemeStore();
const projectStore = useProjectStore();

// 整页背景图：当前工作区 appearance.pageBg
//  - 空 / 找不到 → fallback 到 /images/bg1.jpg
//  - .assets/xxx → IPC 读 blob URL
//  - 外链 / public 路径 → 直接用
const pageBgRel = computed(() => projectStore.currentAppearance.pageBg);
const fsRootRef = computed(() => projectStore.current?.fsRoot ?? "");
const pageBg = useWorkspaceAsset(pageBgRel, fsRootRef, "/images/bg1.jpg");
</script>

<template>
  <!-- ---------------------------------------------- -->
  <!---Main Sidebar -->
  <!-- ---------------------------------------------- -->
  <MainSidebar />
  <!-- ---------------------------------------------- -->
  <!---Top AppBar -->
  <!-- ---------------------------------------------- -->
  <MainAppbar />
  <!-- ---------------------------------------------- -->
  <!---MainArea -->
  <!-- ---------------------------------------------- -->

  <!-- 全屏背景层（fixed 占满视口），跟内容容器解耦 -->
  <div class="page-bg" :style="{ backgroundImage: `url(${pageBg})` }"></div>

  <v-main
    class="main-container"
    v-touch="{
      left: () => (customizeTheme.mainSidebar = false),
      right: () => (customizeTheme.mainSidebar = true),
    }"
  >
    <!-- <GlobalLoading /> -->
    <ToolBox />
    <div class="flex-fill">
      <slot></slot>
    </div>
  </v-main>
</template>

<style scoped>
.scrollnav {
  height: calc(100vh - 326px);
}
.main-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  width: 90%;
  margin: 0 auto;
  /* 背景由 .page-bg 全屏层提供，这里不画背景 */
  background: transparent;
  position: relative;
  z-index: 1; /* 确保内容在背景层之上 */
}

/* 全屏背景层：fixed 占满整个视口，置于内容下方 */
.page-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  pointer-events: none;
}
</style>
