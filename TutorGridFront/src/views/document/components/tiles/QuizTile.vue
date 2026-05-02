<!--
  F14: 测验题磁贴
  - 选择题 + 提交 + AI批改反馈
  - 做题结果可回传后端更新掌握度
-->
<template>
  <v-card class="quiz-tile fill-height" variant="flat" rounded="lg">
    <div class="tile-inner d-flex flex-column">
      <!-- 标题行 -->
      <div class="d-flex align-center gap-2 mb-2">
        <v-icon icon="mdi-help-circle-outline" color="pink" size="18" />
        <span class="text-caption font-weight-bold text-grey-darken-1">测验</span>
        <v-chip v-if="answered" size="x-small" :color="isCorrect ? 'success' : 'error'" variant="tonal">
          {{ isCorrect ? '正确' : '错误' }}
        </v-chip>
      </div>

      <!-- 空状态 -->
      <div
        v-if="!quiz"
        class="d-flex flex-column align-center justify-center flex-fill text-grey"
      >
        <v-icon icon="mdi-school-outline" size="28" class="mb-2" />
        <span class="text-caption">AI 出题中…</span>
        <span class="text-caption text-grey-lighten-1 mt-1">学习知识点后自动生成</span>
      </div>

      <!-- 题目 -->
      <template v-else>
        <div class="text-body-2 font-weight-medium mb-3">
          {{ quiz.question }}
        </div>

        <!-- 选项 -->
        <div class="options-list flex-fill">
          <div
            v-for="(opt, idx) in quiz.options"
            :key="idx"
            class="option-item d-flex align-center pa-2 mb-1 rounded-lg"
            :class="optionClass(idx)"
            @click="onSelect(idx)"
          >
            <v-icon
              :icon="optionIcon(idx)"
              :color="optionColor(idx)"
              size="18"
              class="mr-2 flex-shrink-0"
            />
            <span class="text-body-2">{{ opt }}</span>
          </div>
        </div>

        <!-- 反馈信息 -->
        <v-alert
          v-if="answered"
          :type="isCorrect ? 'success' : 'error'"
          variant="tonal"
          density="compact"
          class="mb-2"
        >
          {{ feedback }}
        </v-alert>

        <!-- 操作按钮 -->
        <div class="d-flex ga-2 mt-auto">
          <v-btn
            v-if="!answered"
            color="primary"
            size="small"
            block
            :disabled="selectedIdx < 0"
            @click="submitAnswer"
          >
            提交答案
          </v-btn>
          <v-btn
            v-else
            variant="tonal"
            size="small"
            block
            @click="reset"
          >
            再来一题
          </v-btn>
        </div>
      </template>
    </div>
  </v-card>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useSnackbarStore } from "@/stores/snackbarStore";

export interface QuizData {
  question: string;
  options: string[];
  answer: number;
  explanation?: string;
}

const props = withDefaults(
  defineProps<{
    quiz?: QuizData | null;
  }>(),
  {
    quiz: null,
  }
);

const emit = defineEmits<{
  submit: [quiz: QuizData, selected: number, correct: boolean];
}>();

const snackbar = useSnackbarStore();

const selectedIdx = ref(-1);
const answered = ref(false);
const isCorrect = ref(false);

const feedback = computed(() => {
  if (!props.quiz) return "";
  if (isCorrect.value) {
    return props.quiz.explanation || "回答正确！继续加油！";
  }
  return props.quiz.explanation || "回答错误，请再试一次。";
});

function onSelect(idx: number) {
  if (answered.value) return;
  selectedIdx.value = idx;
}

function optionClass(idx: number) {
  if (!answered.value) {
    return idx === selectedIdx.value ? "option-selected" : "option-default";
  }
  if (idx === props.quiz?.answer) return "option-correct";
  if (idx === selectedIdx.value && !isCorrect.value) return "option-wrong";
  return "option-default";
}

function optionIcon(idx: number) {
  if (!answered.value) {
    return idx === selectedIdx.value ? "mdi-radiobox-marked" : "mdi-radiobox-blank";
  }
  if (idx === props.quiz?.answer) return "mdi-check-circle";
  if (idx === selectedIdx.value && !isCorrect.value) return "mdi-close-circle";
  return "mdi-radiobox-blank";
}

function optionColor(idx: number) {
  if (!answered.value) return idx === selectedIdx.value ? "primary" : "grey";
  if (idx === props.quiz?.answer) return "success";
  if (idx === selectedIdx.value) return "error";
  return "grey";
}

function submitAnswer() {
  if (selectedIdx.value < 0 || !props.quiz) return;
  answered.value = true;
  isCorrect.value = selectedIdx.value === props.quiz.answer;
  emit("submit", props.quiz, selectedIdx.value, isCorrect.value);
  if (isCorrect.value) {
    snackbar.showSuccessMessage("回答正确！");
  }
}

function reset() {
  selectedIdx.value = -1;
  answered.value = false;
  isCorrect.value = false;
}
</script>

<style scoped lang="scss">
@use "./_styles" as t;

.quiz-tile {
  @include t.frosted-tile;
  @include t.tile-padding;
  height: 100%;

  .tile-inner {
    height: 100%;
    min-height: 160px;
    overflow-y: auto;
  }
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.option-item {
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  border: 1.5px solid transparent;
}

.option-default {
  border-color: rgba(0, 0, 0, 0.08);
  &:hover { background: rgba(0, 0, 0, 0.03); }
}

.option-selected {
  border-color: rgba(33, 150, 243, 0.5);
  background: rgba(33, 150, 243, 0.1);
}

.option-correct {
  border-color: rgba(76, 175, 80, 0.5);
  background: rgba(76, 175, 80, 0.1);
}

.option-wrong {
  border-color: rgba(244, 67, 54, 0.5);
  background: rgba(244, 67, 54, 0.1);
}
</style>
