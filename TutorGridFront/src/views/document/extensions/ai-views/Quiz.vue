<template>
  <v-card
    variant="flat"
    rounded="lg"
    class="ai-quiz pa-3"
    :class="{ 'ai-quiz--selected': selected }"
  >
    <div class="d-flex align-center mb-3">
      <v-icon
        icon="mdi-help-circle-outline"
        size="18"
        color="primary"
        class="mr-2"
      />
      <span class="text-body-2 font-weight-medium flex-fill">测验</span>
      <v-chip size="x-small" variant="tonal" color="primary" class="mr-1">
        {{ questions.length }} 题
      </v-chip>
      <v-btn
        icon="mdi-trash-can-outline"
        size="x-small"
        variant="text"
        @click="deleteNode"
      />
    </div>

    <div v-if="questions.length === 0" class="text-caption text-medium-emphasis">
      暂无题目
    </div>

    <div
      v-for="(q, qi) in questions"
      :key="qi"
      class="ai-quiz__question mb-3"
    >
      <div class="text-body-2 font-weight-medium mb-2">
        {{ qi + 1 }}. {{ q.question }}
      </div>
      <v-radio-group
        :model-value="selectedFor(qi)"
        density="compact"
        hide-details
        class="ai-quiz__options"
        @update:model-value="onSelect(qi, $event)"
      >
        <v-radio
          v-for="(opt, oi) in q.options"
          :key="oi"
          :value="oi"
          :disabled="revealed"
          :color="optionColor(qi, oi)"
        >
          <template #label>
            <span :class="optionLabelClass(qi, oi)">{{ opt }}</span>
            <v-icon
              v-if="revealed && oi === q.answer"
              icon="mdi-check-circle"
              size="16"
              color="success"
              class="ml-2"
            />
            <v-icon
              v-else-if="revealed && selectedFor(qi) === oi"
              icon="mdi-close-circle"
              size="16"
              color="error"
              class="ml-2"
            />
          </template>
        </v-radio>
      </v-radio-group>

      <v-alert
        v-if="revealed && q.explanation"
        density="compact"
        variant="tonal"
        color="primary"
        class="mt-2 ai-quiz__explanation"
      >
        <div class="text-caption font-weight-medium mb-1">解析</div>
        <div class="text-caption">{{ q.explanation }}</div>
      </v-alert>
    </div>

    <v-divider class="my-2" />

    <div class="d-flex align-center">
      <span v-if="revealed" class="text-caption text-medium-emphasis flex-fill">
        正确 {{ correctCount }} / {{ questions.length }}
      </span>
      <span v-else class="text-caption text-medium-emphasis flex-fill">
        已答 {{ answeredCount }} / {{ questions.length }}
      </span>
      <v-btn
        v-if="!revealed"
        size="small"
        variant="tonal"
        color="primary"
        :disabled="answeredCount === 0"
        prepend-icon="mdi-check-all"
        @click="reveal"
      >
        提交
      </v-btn>
      <v-btn
        v-else
        size="small"
        variant="text"
        color="primary"
        prepend-icon="mdi-restart"
        @click="reset"
      >
        重做
      </v-btn>
    </div>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { Node as ProsemirrorNode } from "@tiptap/pm/model";
import type { QuizQuestion, QuizUserState } from "../ai-block-types";

const props = defineProps<{
  node: ProsemirrorNode;
  updateAttributes: (attrs: Record<string, any>) => void;
  deleteNode: () => void;
  selected?: boolean;
}>();

const questions = computed<QuizQuestion[]>(
  () => (props.node.attrs?.data?.questions as QuizQuestion[]) || []
);

const userState = computed<QuizUserState>(
  () => (props.node.attrs?.userState as QuizUserState) || {}
);

const selectedMap = computed<Record<number, number>>(
  () => userState.value.selected || {}
);

const revealed = computed<boolean>(() => !!userState.value.revealed);

const answeredCount = computed(() => Object.keys(selectedMap.value).length);

const correctCount = computed(() => {
  let n = 0;
  questions.value.forEach((q, qi) => {
    if (selectedMap.value[qi] === q.answer) n += 1;
  });
  return n;
});

const selectedFor = (qi: number) =>
  selectedMap.value[qi] === undefined ? null : selectedMap.value[qi];

const writeUserState = (next: QuizUserState) => {
  props.updateAttributes({
    userState: { ...userState.value, ...next },
  });
};

const onSelect = (qi: number, value: number | null) => {
  if (revealed.value || value === null) return;
  const nextSelected = { ...selectedMap.value, [qi]: value };
  writeUserState({ selected: nextSelected });
};

const reveal = () => writeUserState({ revealed: true });
const reset = () => writeUserState({ selected: {}, revealed: false });

const optionColor = (qi: number, oi: number) => {
  if (!revealed.value) return "primary";
  const q = questions.value[qi];
  if (oi === q.answer) return "success";
  if (selectedMap.value[qi] === oi) return "error";
  return "grey";
};

const optionLabelClass = (qi: number, oi: number) => {
  if (!revealed.value) return "";
  const q = questions.value[qi];
  if (oi === q.answer) return "text-success font-weight-medium";
  if (selectedMap.value[qi] === oi) return "text-error";
  return "text-medium-emphasis";
};
</script>

<style scoped lang="scss">
.ai-quiz {
  border: 1px solid rgba(var(--v-theme-primary), 0.32);
  background: rgba(var(--v-theme-primary), 0.03);
}

.ai-quiz--selected {
  border-color: rgb(var(--v-theme-primary));
}

.ai-quiz__question + .ai-quiz__question {
  border-top: 1px dashed rgba(0, 0, 0, 0.08);
  padding-top: 12px;
}

.ai-quiz__options :deep(.v-selection-control) {
  min-height: 32px;
}

.ai-quiz__explanation {
  background: rgba(var(--v-theme-primary), 0.06) !important;
}
</style>
