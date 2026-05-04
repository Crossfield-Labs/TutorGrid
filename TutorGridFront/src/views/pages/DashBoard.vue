<template>
  <div class="pa-5">
    <v-row dense>
      <v-col cols="12" lg="8">
        <v-card class="card-shadow" min-height="420">
          <v-card-title class="d-flex align-center">
            <v-icon color="primary" class="mr-3">mdi-view-dashboard-outline</v-icon>
            <span class="font-weight-bold">MetaAgent 工作区</span>
          </v-card-title>
          <v-card-text>
            <v-row dense>
              <v-col
                v-for="item in workspaceTiles"
                :key="item.title"
                cols="12"
                sm="6"
              >
                <v-sheet
                  class="pa-4 h-100 rounded border workspace-entry"
                  role="button"
                  tabindex="0"
                  @click="openWorkspaceTile(item)"
                  @keydown.enter.prevent="openWorkspaceTile(item)"
                  @keydown.space.prevent="openWorkspaceTile(item)"
                >
                  <div class="d-flex align-center mb-3">
                    <v-icon :color="item.color" class="mr-2">{{ item.icon }}</v-icon>
                    <span class="font-weight-bold">{{ item.title }}</span>
                    <v-icon
                      v-if="item.route"
                      icon="mdi-arrow-top-right"
                      size="16"
                      class="ml-auto text-grey-lighten-1"
                    />
                    <v-chip
                      v-else-if="item.action === 'chat'"
                      size="x-small"
                      variant="tonal"
                      color="info"
                      class="ml-auto"
                    >
                      点击打开
                    </v-chip>
                  </div>
                  <p class="text-body-2 text-medium-emphasis mb-0">
                    {{ item.description }}
                  </p>
                </v-sheet>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="4">
        <v-card class="card-shadow" min-height="420">
          <v-card-title class="d-flex align-center">
            <v-icon color="secondary" class="mr-3">mdi-tune-variant</v-icon>
            <span class="font-weight-bold">桌面化准备</span>
          </v-card-title>
          <v-card-text>
            <v-list density="compact">
              <v-list-item
                v-for="task in desktopTasks"
                :key="task"
                :title="task"
                prepend-icon="mdi-check-circle-outline"
              />
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";

const router = useRouter();

const workspaceTiles = [
  {
    title: "磁贴工作区",
    description: "承载课程资料、便签、任务和 AI 主动推送。",
    icon: "mdi-grid-large",
    color: "primary",
    route: "/board",
  },
  {
    title: "课程知识库",
    description: "为 PPT、PDF、Word 和图片导入预留入口，RAG 自动索引。",
    icon: "mdi-book-open-page-variant-outline",
    color: "success",
    route: "/board",
  },
  {
    title: "Chat 面板",
    description: "打开右侧 AI 抽屉，支持 SSE 流式对话、RAG 引用和联网检索。",
    icon: "mdi-message-text-outline",
    color: "info",
    action: "chat",
  },
  {
    title: "TipTap 文档",
    description: "在工作区创建 Hyper 文档，进入 TipTap 编辑器沉淀笔记和学习产物。",
    icon: "mdi-file-document-edit-outline",
    color: "warning",
    route: "/board",
  },
];

function openWorkspaceTile(item: { route?: string; action?: string }) {
  if (item.action === "chat") {
    const fab = document.querySelector(".chat-fab") as HTMLElement | null;
    if (fab) {
      fab.click();
      return;
    }
    window.dispatchEvent(
      new CustomEvent("tutorgrid:open-chat", {
        detail: { source: "dashboard" },
      })
    );
    return;
  }
  if (item.route) {
    void router.push(item.route);
  }
}

const desktopTasks = [
  "看板工作区 + 磁贴管理系统",
  "Electron 桌面壳 + 文件系统 API",
  "Chat SSE 流式对话 + RAG + Tavily",
  "WebSocket 编排引擎 (task.step/result)",
  "Hyper 文档 TipTap 编辑器 + AI 气泡",
];
</script>

<style scoped lang="scss">
.workspace-entry {
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    box-shadow 0.16s ease,
    transform 0.16s ease;
}

.workspace-entry:hover,
.workspace-entry:focus-visible {
  border-color: rgb(var(--v-theme-primary)) !important;
  box-shadow: 0 8px 24px rgba(31, 42, 68, 0.12);
  outline: none;
  transform: translateY(-1px);
}
</style>
