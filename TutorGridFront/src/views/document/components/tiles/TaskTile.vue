<template>
  <v-card
    class="task-tile d-flex flex-column"
    elevation="0"
    rounded="lg"
    :ripple="false"
  >
    <div class="d-flex align-center mb-2">
      <v-icon color="primary" class="mr-2">mdi-cog-sync-outline</v-icon>
      <span class="text-subtitle-2 font-weight-bold flex-fill">编排任务</span>
      <v-btn
        v-if="task"
        size="x-small"
        variant="text"
        icon="mdi-open-in-new"
        density="comfortable"
        @click="goToDetails"
      />
    </div>

    <div class="d-flex flex-column ga-2 flex-fill">
      <template v-if="task">
        <div class="d-flex align-start justify-space-between ga-2">
          <div class="flex-fill min-w-0">
            <div class="text-body-2 font-weight-bold">
              {{ task.title || "未命名任务" }}
            </div>
            <div v-if="showBodyCopy" class="text-caption text-medium-emphasis mt-1">
              {{ taskStatusCopy(task.status) }}
            </div>
          </div>
          <v-chip size="x-small" :color="stepColor(task.status)" variant="tonal">
            {{ compactMode ? stepStatusLabel(task.status) : currentStepLabel }}
          </v-chip>
        </div>

        <!-- 执行进度 -->
        <div>
          <div class="d-flex align-center justify-space-between text-caption mb-1">
            <span class="text-medium-emphasis">执行进度</span>
            <span class="font-weight-medium">{{ progressLabel }}</span>
          </div>
          <v-progress-linear
            :model-value="progressValue"
            :color="stepColor(task.status)"
            :indeterminate="task.status === 'running' || task.status === 'awaiting_user'"
            :stream="task.status === 'running' || task.status === 'awaiting_user'"
            rounded
          />
        </div>

        <!-- 步骤列表（带状态图标）—— F09 新增 -->
        <div v-if="showStepList" class="step-list">
          <div
            v-for="step in task.steps"
            :key="step.phase"
            class="step-item d-flex align-center ga-2"
          >
            <v-icon
              :icon="stepIcon(step.status)"
              :color="stepColor(step.status)"
              size="16"
              class="flex-shrink-0"
            />
            <span class="text-caption flex-fill">{{ step.name }}</span>
            <v-chip
              size="x-small"
              variant="tonal"
              :color="stepColor(step.status)"
              class="ml-auto"
            >
              {{ stepMiniLabel(step.status) }}
            </v-chip>
          </div>
        </div>

        <!-- 元信息卡片 -->
        <v-row v-if="showMetaList" dense>
          <v-col cols="6">
            <v-card variant="tonal" rounded="lg">
              <v-card-text class="py-2">
                <div class="text-caption text-medium-emphasis">当前阶段</div>
                <div class="text-body-2 font-weight-medium mt-1">{{ currentStepLabel }}</div>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="6">
            <v-card variant="tonal" rounded="lg">
              <v-card-text class="py-2">
                <div class="text-caption text-medium-emphasis">任务状态</div>
                <div class="text-body-2 font-weight-medium mt-1">{{ stepStatusLabel(task.status) }}</div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <v-alert
          v-if="showDetailAlert && task.status === 'done' && task.resultSummary"
          type="success"
          variant="tonal"
          density="compact"
        >
          <MarkdownContent :content="task.resultSummary" />
        </v-alert>

        <v-alert
          v-else-if="showDetailAlert && task.status === 'failed'"
          type="error"
          variant="tonal"
          density="compact"
        >
          <MarkdownContent :content="task.summary || '任务执行失败，请前往详情查看原因。'" />
        </v-alert>

        <v-alert
          v-else-if="showDetailAlert && task.awaitingUser"
          type="warning"
          variant="tonal"
          density="compact"
        >
          <MarkdownContent :content="task.prompt || '任务正在等待补充输入。'" />
        </v-alert>

        <v-text-field
          v-if="task.awaitingUser && showInlineInput"
          v-model="resumeText"
          label="补充输入"
          variant="solo"
          density="comfortable"
          hide-details
        />

        <div class="d-flex ga-2 mt-auto">
          <v-btn
            v-if="task.awaitingUser"
            color="primary"
            size="small"
            :disabled="showInlineInput ? !resumeText.trim() : false"
            @click="openResumeFlow"
          >
            继续执行
          </v-btn>
          <v-btn
            v-if="task.status === 'running' || task.awaitingUser"
            color="warning"
            variant="tonal"
            size="small"
            @click="emit('interrupt')"
          >
            中断
          </v-btn>
          <v-btn
            variant="text"
            size="small"
            class="ml-auto"
            @click="goToDetails"
          >
            查看详情
          </v-btn>
        </div>
      </template>

      <template v-else>
        <v-textarea
          v-if="largeMode"
          v-model="instruction"
          label="输入编排任务"
          placeholder="例如：帮我整理这段笔记并生成一个可运行示例"
          auto-grow
          rows="4"
          variant="solo"
          hide-details
        />
        <div
          v-else
          class="d-flex flex-column justify-center text-center text-caption text-medium-emphasis flex-fill"
        >
          <v-icon icon="mdi-creation-outline" size="26" class="mb-2" />
          <div>{{ compactMode ? "放大磁贴或进入详情发起任务" : "在这里发起一个新的编排任务" }}</div>
        </div>
        <v-btn
          color="primary"
          size="small"
          :loading="starting"
          :disabled="largeMode ? !instruction.trim() : false"
          @click="openStartFlow"
        >
          {{ largeMode ? "启动编排" : "新建任务" }}
        </v-btn>
      </template>
    </div>
  </v-card>

  <v-dialog v-model="startDialog" max-width="560">
    <v-card rounded="lg">
      <v-card-title>新建编排任务</v-card-title>
      <v-card-text>
        <v-textarea
          v-model="instruction"
          label="任务内容"
          placeholder="例如：帮我整理这段笔记并生成一个可运行示例"
          auto-grow
          rows="5"
          variant="solo"
          hide-details
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="startDialog = false">取消</v-btn>
        <v-btn color="primary" :loading="starting" :disabled="!instruction.trim()" @click="submitStart">
          启动
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="resumeDialog" max-width="560">
    <v-card rounded="lg">
      <v-card-title>补充输入</v-card-title>
      <v-card-text>
        <v-textarea
          v-model="resumeText"
          label="输入补充信息"
          auto-grow
          rows="4"
          variant="solo"
          hide-details
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="resumeDialog = false">取消</v-btn>
        <v-btn color="primary" :disabled="!resumeText.trim()" @click="submitResume">
          继续执行
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import MarkdownContent from "@/components/common/MarkdownContent.vue";
import type { OrchestratorTaskItem, TaskStepStatus } from "@/stores/orchestratorTaskStore";

const props = defineProps<{
  task?: OrchestratorTaskItem | null;
  starting?: boolean;
  size?: "1x1" | "1x2" | "2x2";
}>();

const emit = defineEmits<{
  (e: "start", instruction: string): void;
  (e: "resume", content: string): void;
  (e: "interrupt"): void;
}>();

const router = useRouter();
const instruction = ref("");
const resumeText = ref("");
const startDialog = ref(false);
const resumeDialog = ref(false);
const compactMode = computed(() => props.size === "1x1");
const largeMode = computed(() => props.size !== "1x1" && props.size !== "1x2");
const showBodyCopy = computed(() => !compactMode.value);
const showStepList = computed(() => !!props.task && !compactMode.value && props.task.steps.length > 0);
const showMetaList = computed(() => largeMode.value);
const showDetailAlert = computed(() => largeMode.value);
const showInlineInput = computed(() => largeMode.value);
const currentStep = computed(() => {
  if (!props.task) return null;
  return props.task.steps.find((step) => step.index === props.task.currentStepIndex) || props.task.steps[0] || null;
});
const currentStepLabel = computed(() => currentStep.value?.name || "等待开始");
const progressValue = computed(() => {
  if (!props.task) return 0;
  if (props.task.status === "done") return 100;
  if (props.task.status === "failed") return Math.max(25, props.task.currentStepIndex * 25);
  const base = Math.max(0, props.task.currentStepIndex - 1) * 25;
  if (props.task.status === "running") return base + 15;
  if (props.task.status === "awaiting_user") return base + 20;
  if (props.task.status === "interrupted") return base + 10;
  return base + 5;
});
const progressLabel = computed(() => {
  if (!props.task) return "";
  if (props.task.status === "done") return "已完成";
  if (props.task.status === "failed") return "执行失败";
  if (props.task.status === "awaiting_user") return "等待补充输入";
  if (props.task.status === "interrupted") return "已中断";
  if (props.task.status === "running") return "执行中";
  return "排队中";
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

function stepMiniLabel(status: TaskStepStatus) {
  if (status === "done") return "✅";
  if (status === "failed") return "❌";
  if (status === "running") return "🔄";
  if (status === "awaiting_user") return "⏳";
  if (status === "interrupted") return "⏸";
  return "⏳";
}

function stepStatusLabel(status: TaskStepStatus) {
  if (status === "done") return "已完成";
  if (status === "failed") return "失败";
  if (status === "running") return "执行中";
  if (status === "awaiting_user") return "待输入";
  if (status === "interrupted") return "已中断";
  return "待处理";
}

function taskStatusCopy(status: TaskStepStatus) {
  if (status === "done") return "编排已完成，可前往详情查看完整步骤与结果。";
  if (status === "failed") return "编排未完成，可前往详情查看失败阶段。";
  if (status === "awaiting_user") return "当前需要补充输入后才能继续。";
  if (status === "interrupted") return "任务已暂停，可稍后恢复或查看详情。";
  if (status === "running") return "正在逐步推进编排流程。";
  return "任务已创建，等待进入执行阶段。";
}

function submitResume() {
  const value = resumeText.value.trim();
  if (!value) return;
  emit("resume", value);
  resumeText.value = "";
  resumeDialog.value = false;
}

function openResumeFlow() {
  if (showInlineInput.value) {
    submitResume();
    return;
  }
  resumeDialog.value = true;
}

function openStartFlow() {
  if (largeMode.value) {
    submitStart();
    return;
  }
  startDialog.value = true;
}

function submitStart() {
  const value = instruction.value.trim();
  if (!value) return;
  emit("start", value);
  instruction.value = "";
  startDialog.value = false;
}

function goToDetails() {
  if (!props.task) return;
  void router.push(`/tasks/${props.task.taskId}`);
}
</script>

<style scoped lang="scss">
@use "./_styles" as t;

.task-tile {
  @include t.frosted-tile;
  @include t.tile-padding;
  height: 100%;
  width: 100%;
  overflow-y: auto;
}

.step-list {
  display: flex;
  flex-direction: column;
  gap: 3px;

  .step-item {
    padding: 4px 8px;
    border-radius: 6px;
    background: rgba(0, 0, 0, 0.03);
  }
}

:global(.v-theme--dark) .task-tile {
  @include t.frosted-tile-dark;

  .step-item {
    background: rgba(255, 255, 255, 0.04);
  }
}
</style>
