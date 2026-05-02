<template>
  <div class="pa-5">
    <v-row dense>
      <!-- ============ 主内容区 ============ -->
      <v-col cols="12" lg="8">
        <v-card min-height="420">
          <v-card-title class="d-flex align-center">
            <v-btn variant="text" prepend-icon="mdi-arrow-left" class="mr-3" @click="goBack">返回</v-btn>
            <v-icon :color="task ? stepColor(task.status) : 'grey'" class="mr-3">mdi-cog-sync-outline</v-icon>
            <div class="flex-fill">
              <div class="font-weight-bold">编排详情</div>
              <div class="text-body-2 text-medium-emphasis">{{ task?.title || '任务详情' }}</div>
            </div>
          </v-card-title>

          <!-- 有任务数据 -->
          <v-card-text v-if="task">
            <!-- 步骤进度 -->
            <div class="mb-4">
              <div class="d-flex align-center justify-space-between text-caption mb-2">
                <span class="text-medium-emphasis">执行进度</span>
                <span class="font-weight-medium">{{ progressLabel }}</span>
              </div>
              <v-progress-linear
                :model-value="progressValue"
                :color="stepColor(task.status)"
                :indeterminate="task.status === 'running' || task.status === 'awaiting_user'"
                rounded
                height="6"
              />
            </div>

            <!-- 步骤时间线 -->
            <div class="step-timeline mb-4">
              <div
                v-for="step in task.steps"
                :key="step.phase"
                class="step-row d-flex ga-3 mb-2"
              >
                <div class="step-dot-col d-flex flex-column align-center">
                  <div class="step-dot" :class="`dot-${step.status}`">
                    <v-icon :icon="stepIcon(step.status)" size="14" color="white" />
                  </div>
                  <div v-if="step.index < task.steps.length" class="step-line" :class="`line-${step.status}`" />
                </div>
                <div class="flex-fill pb-3">
                  <div class="d-flex align-center ga-2">
                    <span class="text-body-2 font-weight-medium">{{ step.name }}</span>
                    <v-chip size="x-small" :color="stepColor(step.status)" variant="tonal">
                      {{ stepStatusLabel(step.status) }}
                    </v-chip>
                  </div>
                  <div v-if="step.detail" class="text-caption text-grey-darken-1 mt-1 step-detail">
                    <MarkdownContent :content="step.detail" />
                  </div>
                </div>
              </div>
            </div>

            <!-- 结果摘要 -->
            <v-card variant="tonal" :color="task.status === 'done' ? 'success' : task.status === 'failed' ? 'error' : 'primary'" class="mt-4">
              <v-card-text>
                <div class="text-subtitle-2 font-weight-bold mb-2">
                  {{ task.status === 'done' ? '✅ 任务完成' : task.status === 'failed' ? '❌ 任务失败' : '📋 结果摘要' }}
                </div>
                <div class="text-body-2">
                  <MarkdownContent :content="task.resultSummary || task.summary || '等待任务完成…'" />
                </div>
              </v-card-text>
            </v-card>
          </v-card-text>

          <!-- 空状态 -->
          <v-card-text v-else class="d-flex flex-column align-center justify-center fill-height py-12">
            <v-icon icon="mdi-cog-off-outline" size="64" color="grey-lighten-1" class="mb-4" />
            <div class="text-h6 text-medium-emphasis mb-2">未找到任务</div>
            <div class="text-body-2 text-grey-darken-1 mb-4 text-center" style="max-width: 400px">
              当前 URL 中的任务 ID 没有匹配的编排记录。<br />
              请从 Hyper 文档中输入 <code>/task</code> 命令启动编排任务。
            </div>
            <v-btn
              prepend-icon="mdi-arrow-left"
              variant="tonal"
              @click="router.push('/board')"
            >
              回到工作区
            </v-btn>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- ============ 侧栏 ============ -->
      <v-col cols="12" lg="4">
        <v-card min-height="420">
          <v-card-title class="d-flex align-center">
            <v-icon color="secondary" class="mr-3">mdi-information-outline</v-icon>
            <span class="font-weight-bold">任务信息</span>
          </v-card-title>
          <v-card-text v-if="task">
            <v-list density="compact">
              <v-list-item title="任务 ID" :subtitle="ellipsis(task.taskId, 20)" prepend-icon="mdi-pound" />
              <v-list-item title="关联文档" :subtitle="task.docId || '未关联'" prepend-icon="mdi-file-document-outline">
                <template v-if="task.docId" #append>
                  <v-btn icon="mdi-open-in-new" variant="text" size="x-small" @click="router.push(`/hyperdoc/${task.docId}`)" />
                </template>
              </v-list-item>
              <v-list-item title="当前阶段" :subtitle="task.phase" prepend-icon="mdi-flag-outline" />
              <v-list-item title="状态" prepend-icon="mdi-check-decagram-outline">
                <template #subtitle>
                  <v-chip size="x-small" :color="stepColor(task.status)" variant="tonal">
                    {{ stepStatusLabel(task.status) }}
                  </v-chip>
                </template>
              </v-list-item>
              <v-list-item title="更新于" :subtitle="formatTime(task.updatedAt)" prepend-icon="mdi-clock-outline" />
            </v-list>

            <!-- 产物文件 -->
            <v-divider class="my-3" />
            <div class="text-caption font-weight-bold text-grey-darken-1 mb-2">
              产物文件 ({{ task.artifacts.length }})
            </div>
            <div v-if="task.artifacts.length" class="artifact-list">
              <div
                v-for="(a, i) in task.artifacts"
                :key="i"
                class="artifact-item d-flex align-center pa-2 mb-1 rounded"
              >
                <v-icon
                  :icon="a.type === 'image' ? 'mdi-file-image' : 'mdi-code-tags'"
                  size="18"
                  class="mr-2"
                  :color="a.type === 'image' ? 'green' : 'blue'"
                />
                <span class="text-caption text-truncate flex-fill">{{ a.path || a.type }}</span>
              </div>
            </div>
            <div v-else class="text-caption text-grey">
              暂无产物文件
            </div>
          </v-card-text>
          <v-card-text v-else class="d-flex align-center justify-center fill-height">
            <span class="text-caption text-grey">—</span>
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

const progressValue = computed(() => {
  if (!task.value) return 0;
  if (task.value.status === "done") return 100;
  if (task.value.status === "failed") return 50;
  return Math.max(5, (task.value.currentStepIndex - 1) * 25 + 12);
});

const progressLabel = computed(() => {
  if (!task.value) return "";
  if (task.value.status === "done") return "已完成";
  if (task.value.status === "failed") return "执行失败";
  return `Step ${task.value.currentStepIndex}/${task.value.stepTotal}`;
});

function stepIcon(status: TaskStepStatus) {
  const map: Record<string, string> = {
    done: "mdi-check",
    failed: "mdi-close",
    running: "mdi-progress-clock",
    awaiting_user: "mdi-account-clock-outline",
    interrupted: "mdi-pause",
  };
  return map[status] || "mdi-circle-outline";
}

function stepColor(status: TaskStepStatus) {
  const map: Record<string, string> = {
    done: "success",
    failed: "error",
    running: "primary",
    awaiting_user: "warning",
    interrupted: "warning",
  };
  return map[status] || "grey";
}

function stepStatusLabel(status: TaskStepStatus) {
  const map: Record<string, string> = {
    done: "已完成",
    failed: "失败",
    running: "执行中",
    awaiting_user: "待输入",
    interrupted: "已中断",
  };
  return map[status] || "待处理";
}

function ellipsis(text: string, max: number) {
  if (!text) return "";
  return text.length > max ? text.slice(0, max) + "…" : text;
}

function formatTime(iso: string) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

function goBack() {
  if (window.history.length > 1) { router.back(); return; }
  void router.push("/board");
}
</script>

<style scoped lang="scss">
.step-timeline {
  .step-row { align-items: flex-start; }
  .step-dot-col { width: 28px; flex-shrink: 0; }
  .step-dot {
    width: 24px; height: 24px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;

    &.dot-done { background: rgb(var(--v-theme-success)); }
    &.dot-running { background: rgb(var(--v-theme-primary)); animation: pulse 1.5s infinite; }
    &.dot-failed { background: rgb(var(--v-theme-error)); }
    &.dot-awaiting_user { background: rgb(var(--v-theme-warning)); }
    &.dot-interrupted { background: rgb(var(--v-theme-warning)); }
    &.dot-pending { background: #ccc; }
  }
  .step-line {
    width: 2px; flex: 1; min-height: 16px;
    &.line-done { background: rgb(var(--v-theme-success)); }
    &.line-running { background: rgb(var(--v-theme-primary)); }
    &.line-pending, &.line-failed { background: #e0e0e0; }
    &.line-interrupted { background: rgb(var(--v-theme-warning)); }
  }
  .step-detail { max-width: 100%; overflow-x: auto; }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.artifact-item {
  background: rgba(0, 0, 0, 0.03);
}

code {
  background: rgba(0,0,0,0.06);
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 0.9em;
}
</style>
