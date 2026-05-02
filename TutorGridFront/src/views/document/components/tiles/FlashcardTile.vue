<!--
  F14: 闪卡磁贴
  - 正面问题 / 背面答案
  - 点击翻转动画 (CSS 3D transform)
-->
<template>
  <v-card class="flashcard-tile fill-height" variant="flat" rounded="lg">
    <div class="tile-inner d-flex flex-column">
      <!-- 标题行 -->
      <div class="d-flex align-center gap-2 mb-2">
        <v-icon icon="mdi-card-bulleted-outline" color="amber" size="18" />
        <span class="text-caption font-weight-bold text-grey-darken-1">闪卡</span>
        <v-chip v-if="cards.length" size="x-small" variant="tonal" class="ml-auto">
          {{ currentIdx + 1 }}/{{ cards.length }}
        </v-chip>
      </div>

      <!-- 空状态 -->
      <div
        v-if="!cards.length"
        class="d-flex flex-column align-center justify-center flex-fill text-grey"
      >
        <v-icon icon="mdi-cards-outline" size="28" class="mb-2" />
        <span class="text-caption">AI 闪卡生成中…</span>
        <span class="text-caption text-grey-lighten-1 mt-1">学习后自动生成知识点闪卡</span>
      </div>

      <!-- 闪卡 -->
      <template v-else>
        <div class="flashcard-wrapper flex-fill" @click="flip">
          <div class="flashcard" :class="{ 'is-flipped': flipped }">
            <!-- 正面：问题 -->
            <div class="flashcard-face flashcard-front">
              <div class="face-content d-flex flex-column align-center justify-center text-center pa-4">
                <v-icon icon="mdi-help" size="20" class="mb-2 text-grey-lighten-1" />
                <div class="text-body-2">{{ currentCard.front }}</div>
                <div class="text-caption text-grey-darken-1 mt-3">
                  点击翻转查看答案
                </div>
              </div>
            </div>
            <!-- 背面：答案 -->
            <div class="flashcard-face flashcard-back">
              <div class="face-content d-flex flex-column align-center justify-center text-center pa-4">
                <v-icon icon="mdi-lightbulb-on-outline" size="20" class="mb-2 text-amber" />
                <div class="text-body-2">{{ currentCard.back }}</div>
                <div class="text-caption text-grey-darken-1 mt-3">
                  点击返回
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 导航按钮 -->
        <div class="d-flex justify-center ga-2 mt-2">
          <v-btn
            icon="mdi-chevron-left"
            variant="text"
            size="small"
            :disabled="currentIdx <= 0"
            @click="prev"
          />
          <v-btn
            v-for="(_, idx) in cards"
            :key="idx"
            :color="idx === currentIdx ? 'primary' : 'grey-lighten-1'"
            variant="text"
            size="x-small"
            icon
            @click="goTo(idx)"
          >
            {{ idx + 1 }}
          </v-btn>
          <v-btn
            icon="mdi-chevron-right"
            variant="text"
            size="small"
            :disabled="currentIdx >= cards.length - 1"
            @click="next"
          />
        </div>
      </template>
    </div>
  </v-card>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

export interface Flashcard {
  front: string;
  back: string;
}

const props = withDefaults(
  defineProps<{
    cards?: Flashcard[];
  }>(),
  {
    cards: () => [],
  }
);

const currentIdx = ref(0);
const flipped = ref(false);

const currentCard = computed(() => props.cards[currentIdx.value] || { front: "", back: "" });

function flip() {
  flipped.value = !flipped.value;
}

function prev() {
  if (currentIdx.value > 0) {
    currentIdx.value--;
    flipped.value = false;
  }
}

function next() {
  if (currentIdx.value < props.cards.length - 1) {
    currentIdx.value++;
    flipped.value = false;
  }
}

function goTo(idx: number) {
  currentIdx.value = idx;
  flipped.value = false;
}
</script>

<style scoped lang="scss">
@use "./_styles" as t;

.flashcard-tile {
  @include t.frosted-tile;
  @include t.tile-padding;
  height: 100%;

  .tile-inner {
    height: 100%;
    min-height: 160px;
  }
}

// 3D 翻转容器
.flashcard-wrapper {
  perspective: 800px;
  cursor: pointer;
}

.flashcard {
  width: 100%;
  height: 100%;
  min-height: 110px;
  position: relative;
  transform-style: preserve-3d;
  transition: transform 0.5s ease;
  border-radius: 8px;

  &.is-flipped {
    transform: rotateY(180deg);
  }
}

.flashcard-face {
  position: absolute;
  inset: 0;
  backface-visibility: hidden;
  border-radius: 8px;
  border: 1.5px solid rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
}

.flashcard-front {
  background: rgba(255, 255, 255, 0.9);
}

.flashcard-back {
  background: rgba(255, 248, 225, 0.9);
  transform: rotateY(180deg);
}

.face-content {
  width: 100%;
  height: 100%;
}
</style>
