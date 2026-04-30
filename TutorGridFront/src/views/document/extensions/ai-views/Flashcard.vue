<template>
  <v-card
    variant="flat"
    rounded="lg"
    class="ai-flashcard pa-3"
    :class="{ 'ai-flashcard--selected': selected }"
  >
    <div class="d-flex align-center mb-3">
      <v-icon
        icon="mdi-cards-outline"
        size="18"
        color="primary"
        class="mr-2"
      />
      <span class="text-body-2 font-weight-medium flex-fill">闪卡</span>
      <v-chip size="x-small" variant="tonal" color="primary" class="mr-1">
        {{ index + 1 }} / {{ cards.length || 1 }}
      </v-chip>
      <v-btn
        icon="mdi-trash-can-outline"
        size="x-small"
        variant="text"
        @click="deleteNode"
      />
    </div>

    <div v-if="cards.length === 0" class="text-caption text-medium-emphasis py-4 text-center">
      暂无闪卡
    </div>

    <div
      v-else
      class="ai-flashcard__stage"
      :class="{ 'ai-flashcard__stage--flipped': isFlipped }"
      role="button"
      tabindex="0"
      @click="toggleFlip"
      @keyup.enter="toggleFlip"
      @keyup.space.prevent="toggleFlip"
    >
      <div class="ai-flashcard__inner">
        <div class="ai-flashcard__face ai-flashcard__face--front">
          <div class="text-overline text-medium-emphasis mb-1">问题</div>
          <div class="text-body-1 font-weight-medium">
            {{ current.front }}
          </div>
          <div class="ai-flashcard__hint text-caption text-medium-emphasis mt-3">
            <v-icon icon="mdi-cursor-default-click-outline" size="14" class="mr-1" />
            点击翻面
          </div>
        </div>
        <div class="ai-flashcard__face ai-flashcard__face--back">
          <div class="text-overline text-medium-emphasis mb-1">答案</div>
          <div class="text-body-2">
            {{ current.back }}
          </div>
        </div>
      </div>
    </div>

    <v-divider class="my-2" v-if="cards.length > 0" />

    <div v-if="cards.length > 0" class="d-flex align-center">
      <v-btn
        icon="mdi-chevron-left"
        size="small"
        variant="text"
        :disabled="index === 0"
        @click="goPrev"
      />
      <v-btn
        icon="mdi-chevron-right"
        size="small"
        variant="text"
        :disabled="index >= cards.length - 1"
        @click="goNext"
      />
      <v-spacer />
      <v-btn
        size="small"
        variant="text"
        color="primary"
        prepend-icon="mdi-restart"
        @click="resetAll"
      >
        重置
      </v-btn>
    </div>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { Node as ProsemirrorNode } from "@tiptap/pm/model";
import type { FlashcardItem, FlashcardUserState } from "../ai-block-types";

const props = defineProps<{
  node: ProsemirrorNode;
  updateAttributes: (attrs: Record<string, any>) => void;
  deleteNode: () => void;
  selected?: boolean;
}>();

const cards = computed<FlashcardItem[]>(
  () => (props.node.attrs?.data?.cards as FlashcardItem[]) || []
);

const userState = computed<FlashcardUserState>(
  () => (props.node.attrs?.userState as FlashcardUserState) || {}
);

const index = computed(() => Math.min(userState.value.index || 0, Math.max(cards.value.length - 1, 0)));
const flippedMap = computed<Record<number, boolean>>(
  () => userState.value.flipped || {}
);
const isFlipped = computed(() => !!flippedMap.value[index.value]);

const current = computed(
  () => cards.value[index.value] || { front: "", back: "" }
);

const writeUserState = (next: FlashcardUserState) => {
  props.updateAttributes({
    userState: { ...userState.value, ...next },
  });
};

const toggleFlip = () => {
  const next = { ...flippedMap.value, [index.value]: !isFlipped.value };
  writeUserState({ flipped: next });
};

const goPrev = () => {
  if (index.value > 0) writeUserState({ index: index.value - 1 });
};

const goNext = () => {
  if (index.value < cards.value.length - 1) {
    writeUserState({ index: index.value + 1 });
  }
};

const resetAll = () => writeUserState({ index: 0, flipped: {} });
</script>

<style scoped lang="scss">
.ai-flashcard {
  border: 1px solid rgba(var(--v-theme-primary), 0.32);
  background: rgba(var(--v-theme-primary), 0.03);
}

.ai-flashcard--selected {
  border-color: rgb(var(--v-theme-primary));
}

.ai-flashcard__stage {
  perspective: 1200px;
  cursor: pointer;
  outline: none;
}

.ai-flashcard__stage:focus-visible .ai-flashcard__inner {
  box-shadow: 0 0 0 2px rgb(var(--v-theme-primary));
}

.ai-flashcard__inner {
  position: relative;
  width: 100%;
  min-height: 140px;
  transform-style: preserve-3d;
  transition: transform 420ms cubic-bezier(0.4, 0.2, 0.2, 1);
  border-radius: 10px;
}

.ai-flashcard__stage--flipped .ai-flashcard__inner {
  transform: rotateX(180deg);
}

.ai-flashcard__face {
  position: absolute;
  inset: 0;
  padding: 16px 18px;
  background: #fff;
  border: 1px solid rgba(var(--v-theme-primary), 0.18);
  border-radius: 10px;
  backface-visibility: hidden;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.ai-flashcard__face--back {
  transform: rotateX(180deg);
  background: rgba(var(--v-theme-primary), 0.05);
}

.ai-flashcard__hint {
  position: absolute;
  right: 14px;
  bottom: 10px;
  display: flex;
  align-items: center;
}
</style>
