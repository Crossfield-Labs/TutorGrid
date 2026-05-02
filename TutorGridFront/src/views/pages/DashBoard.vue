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
                  class="pa-4 h-100 rounded border dash-tile"
                  :class="{ clickable: item.to || item.action }"
                  @click="onTileClick(item)"
                >
                  <div class="d-flex align-center mb-3">
                    <v-icon :color="item.color" class="mr-2">{{ item.icon }}</v-icon>
                    <span class="font-weight-bold">{{ item.title }}</span>
                    <v-icon
                      v-if="item.to"
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
    description: "看板式工作区：管理课程资料、便签、任务和 AI 主动推送。",
    icon: "mdi-grid-large",
    color: "primary",
    to: "/board",
  },
  {
    title: "课程知识库",
    description: "在工作区中导入 PPT、PDF、Word 和图片，RAG 自动索引。",
    icon: "mdi-book-open-page-variant-outline",
    color: "success",
    to: "/board",
  },
  {
    title: "Chat 面板",
    description: "右下角 AI 对话，SSE 流式回答 + RAG + Tavily 联网搜索。",
    icon: "mdi-message-text-outline",
    color: "info",
    action: "chat",
  },
  {
    title: "TipTap 文档",
    description: "在工作区中创建 Hyper 文档，进入 TipTap 编辑器。",
    icon: "mdi-file-document-edit-outline",
    color: "warning",
    to: "/board",
  },
];

function onTileClick(item: (typeof workspaceTiles)[number]) {
  if (item.to) {
    router.push(item.to);
  } else if (item.action === "chat") {
    const fab = document.querySelector(".chat-fab") as HTMLElement | null;
    if (fab) fab.click();
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

<style scoped>
.dash-tile.clickable {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}
.dash-tile.clickable:hover {
  transform: translateY(-3px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}
</style>
