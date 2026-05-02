<template>
  <div class="pa-5">
    <v-row dense>
      <v-col cols="12" lg="8">
        <v-card min-height="420">
          <v-card-title class="d-flex align-center">
            <v-btn
              variant="text"
              prepend-icon="mdi-arrow-left"
              class="mr-3"
              @click="goBack"
            >
              返回
            </v-btn>
            <v-icon color="primary" class="mr-3">mdi-view-list-outline</v-icon>
            <div class="flex-fill">
              <div class="font-weight-bold">编排详情</div>
              <div class="text-body-2 text-medium-emphasis">
                {{ task?.title || "任务详情" }}
              </div>
            </div>
          </v-card-title>
          <v-card-text v-if="task">
            <v-stepper :model-value="task.currentStepIndex" alt-labels flat class="mb-4">
              <v-stepper-header>
                <template v-for="step in task.steps" :key="step.phase">
                  <v-stepper-item
                    :value="step.index"
                    :title="`Step ${step.index}`"
                    :subtitle="step.name"
                    :complete="step.status === 'done'"
                    :color="stepColor(step.status)"
                    :icon="stepIcon(step.status)"
                  />
                </template>
              </v-stepper-header>
            </v-stepper>

            <v-expansion-panels variant="accordion">
              <v-expansion-panel v-for="step in task.steps" :key="step.phase">
                <v-expansion-panel-title>
                  <div class="d-flex align-center w-100">
                    <v-icon :color="stepColor(step.status)" class="mr-2">
                      {{ stepIcon(step.status) }}
                    </v-icon>
                    <span class="flex-fill">{{ step.name }}</span>
                    <v-chip size="x-small" :color="stepColor(step.status)" variant="tonal">
                      {{ stepStatusLabel(step.status) }}
                    </v-chip>
                  </div>
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <MarkdownContent
                    v-if="step.index === task.currentStepIndex"
                    :content="task.summary || task.resultSummary || '暂无详情'"
                  />
                  <span v-else>该步骤尚无更多详情</span>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>

            <v-card variant="tonal" color="primary" class="mt-4">
              <v-card-text>
                <div class="text-subtitle-2 font-weight-bold mb-2">结果摘要</div>
                <div class="text-body-2">
                  <MarkdownContent :content="task.resultSummary || '任务尚未完成'" />
                </div>
              </v-card-text>
            </v-card>
          </v-card-text>
          <v-card-text v-else>
            <div class="text-body-2 text-medium-emphasis">
              未找到任务，请先从文档页启动一个编排任务。
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="4">
        <v-card min-height="420">
          <v-card-title class="d-flex align-center">
            <v-icon color="secondary" class="mr-3">mdi-information-outline</v-icon>
            <span class="font-weight-bold">任务状态</span>
          </v-card-title>
          <v-card-text v-if="task">
            <v-list density="comfortable">
              <v-list-item title="任务 ID" :subtitle="task.taskId" prepend-icon="mdi-pound" />
              <v-list-item title="会话 ID" :subtitle="task.sessionId" prepend-icon="mdi-connection" />
              <v-list-item title="文档 ID" :subtitle="task.docId || '未关联'" prepend-icon="mdi-file-document-outline" />
              <v-list-item title="当前阶段" :subtitle="task.phase" prepend-icon="mdi-flag-outline" />
              <v-list-item title="当前状态" :subtitle="stepStatusLabel(task.status)" prepend-icon="mdi-check-decagram-outline" />
              <v-list-item title="最近更新" :subtitle="task.updatedAt" prepend-icon="mdi-clock-outline" />
            </v-list>
            <v-divider class="my-4" />
            <v-chip-group column>
              <v-chip color="primary" variant="tonal">
                {{ task.awaitingUser ? "等待输入" : "运行中或已完成" }}
              </v-chip>
              <v-chip color="info" variant="tonal">
                产物 {{ task.artifacts.length }}
              </v-chip>
            </v-chip-group>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import MarkdownContent from "@/components/common/MarkdownContent.vue";
import { useOrchestratorTaskStore, type TaskStepStatus } from "@/stores/orchestratorTaskStore";

const route = useRoute();
const router = useRouter();
const taskStore = useOrchestratorTaskStore();

const task = computed(() => {
  const taskId = String(route.params.taskId || "");
  return taskId ? taskStore.tasksById[taskId] || null : null;
});

function stepIcon(status: TaskStepStatus) {
  if (status === "done") return "mdi-check-circle";
  if (status === "failed") return "mdi-close-circle";
  if (status === "running") return "mdi-progress-clock";
  if (status === "awaiting_user") return "mdi-account-clock-outline";
  if (status === "interrupted") return "mdi-pause-circle";
  return "mdi-timer-sand-empty";
}

function stepColor(status: TaskStepStatus) {
  if (status === "done") return "success";
  if (status === "failed") return "error";
  if (status === "running") return "primary";
  if (status === "awaiting_user") return "warning";
  if (status === "interrupted") return "warning";
  return "grey";
}

function stepStatusLabel(status: TaskStepStatus) {
  if (status === "done") return "已完成";
  if (status === "failed") return "失败";
  if (status === "running") return "执行中";
  if (status === "awaiting_user") return "待输入";
  if (status === "interrupted") return "已中断";
  return "待处理";
}

function goBack() {
  if (window.history.length > 1) {
    router.back();
    return;
  }
  void router.push("/board");
}
</script>
