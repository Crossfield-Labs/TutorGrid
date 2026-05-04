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
                <v-sheet class="pa-4 h-100 rounded border">
                  <div class="d-flex align-center mb-3">
                    <v-icon :color="item.color" class="mr-2">{{ item.icon }}</v-icon>
                    <span class="font-weight-bold">{{ item.title }}</span>
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
const workspaceTiles = [
  {
    title: "磁贴工作区",
    description: "后续承载课程资料、便签、任务和 AI 主动推送。",
    icon: "mdi-grid-large",
    color: "primary",
  },
  {
    title: "课程知识库",
    description: "为 PPT、PDF、Word 和图片导入预留入口。",
    icon: "mdi-book-open-page-variant-outline",
    color: "success",
  },
  {
    title: "Chat 面板",
    description: "后续接入 WebSocket 流式对话和编排事件。",
    icon: "mdi-message-text-outline",
    color: "info",
  },
  {
    title: "TipTap 文档",
    description: "用于笔记、AI 命令和学习产物沉淀。",
    icon: "mdi-file-document-edit-outline",
    color: "warning",
  },
];

const desktopTasks = [
  "清理模板依赖",
  "建立 Electron 主进程",
  "建立 preload 安全桥",
  "规划本地数据目录",
  "接入后端健康检查",
];
</script>
