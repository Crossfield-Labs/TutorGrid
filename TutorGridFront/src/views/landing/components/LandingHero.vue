<script setup lang="ts">
import { onMounted, ref } from "vue";
import { FIGMA_ASSETS as A } from "../assets";
import { gentleFloat } from "../composables/useLandingAnimations";

const floaters = ref<HTMLElement[]>([]);

onMounted(() => {
  // 4 个图标错开起步时间 + 振幅微差，避免整齐齐"机械感"
  const phases = [0, 1.2, 0.6, 1.8];
  const amps = [7, 5, 6, 8];
  floaters.value.forEach((el, i) => {
    if (el) gentleFloat(el, amps[i], phases[i]);
  });
});
</script>

<template>
  <section class="landing-hero" data-node-id="0:105">
    <div class="landing-hero__row">
      <!-- 左侧两个圆形图标（错位排布） -->
      <div class="landing-hero__icon-cluster left" data-node-id="0:108">
        <div
          class="landing-hero__circle landing-hero__circle--green-light"
          :ref="(el) => { if (el) floaters[0] = el as HTMLElement; }"
          data-node-id="0:110"
        >
          <v-icon size="32" color="#004a30">mdi-head-lightbulb</v-icon>
        </div>
        <div
          class="landing-hero__circle landing-hero__circle--green-deep offset-down"
          :ref="(el) => { if (el) floaters[1] = el as HTMLElement; }"
          data-node-id="0:115"
        >
          <v-icon size="32" color="#fff">mdi-file-document-edit-outline</v-icon>
        </div>
      </div>

      <!-- 中间标题 -->
      <h1 class="landing-hero__title" data-node-id="0:120">
        <span>格智&nbsp;</span>
        <span class="landing-pill-highlight" data-node-id="0:122">
          <span>生境</span>
        </span>
        <span>&nbsp;TutorGrid</span>
        <span>&nbsp;基于多智能体编排的磁贴式自适应学伴</span>
      </h1>

      <!-- 右侧装饰：圆形图标 + 描边箭头 -->
      <div class="landing-hero__icon-cluster right" data-node-id="0:126">
        <div
          class="landing-hero__circle landing-hero__circle--green-light offset-right"
          :ref="(el) => { if (el) floaters[2] = el as HTMLElement; }"
          data-node-id="0:128"
        >
          <v-icon size="32" color="#004a30">mdi-view-grid-outline</v-icon>
        </div>
        <div
          class="landing-hero__circle landing-hero__circle--outlined offset-down-2"
          :ref="(el) => { if (el) floaters[3] = el as HTMLElement; }"
          data-node-id="0:133"
        >
          <v-icon size="32" color="#333">mdi-robot-outline</v-icon>
        </div>
      </div>
    </div>

    <div class="landing-hero__sub" data-node-id="0:138">
      <p class="landing-hero__subtitle">
        你记两句，Copilot 帮你整理好；你写一句"帮我跑"，编排引擎就替你做了。
      </p>
      <div class="landing-hero__cta-wrap">
        <button class="landing-hero__cta" data-node-id="0:141" v-ripple>
          <span>立即体验</span>
          <v-icon size="20" color="#004a30">mdi-arrow-right</v-icon>
        </button>
      </div>
    </div>
  </section>
</template>

<style lang="scss" scoped>
.landing-hero {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 20px;
  align-items: center;
  justify-content: center;
  padding: 40px 0;

  &__row {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 50px;
  }

  &__icon-cluster {
    position: relative;
    display: inline-grid;
    place-items: start;

    &.left {
      width: auto;
    }
    &.right {
      width: 128px;
    }
  }

  &__circle {
    grid-column: 1;
    grid-row: 1;
    display: inline-flex;
    align-items: center;
    padding: 14px;
    border-radius: var(--landing-r-circle);

    img {
      width: 32px;
      height: 32px;
      display: block;
      border-radius: 10px;
      overflow: hidden;
    }

    &--green-light {
      background: var(--landing-green-light-2);
    }
    &--green-deep {
      background: var(--landing-green-deep);
    }
    &--outlined {
      border: 2px solid var(--landing-gray-line);
    }

    // 错位偏移（按 Figma ml/mt 指定）
    &.offset-down {
      margin-left: 52px;
      margin-top: 70px;
    }
    &.offset-right {
      margin-left: 68px;
    }
    &.offset-down-2 {
      margin-top: 60px;
    }
  }

  &__title {
    width: 527px;
    display: flex;
    flex-wrap: wrap;
    gap: 1px;
    align-items: center;
    justify-content: center;
    font-family: "Inter", sans-serif;
    font-weight: 700;
    font-size: var(--landing-fs-hero);
    line-height: normal;
    color: #000;
    text-align: center;
    text-transform: uppercase;
    margin: 0;

    .landing-pill-highlight {
      // 让胶囊里的文字保持同样字号
      font-weight: 700;
      font-size: var(--landing-fs-hero);
      line-height: normal;
      text-transform: uppercase;
    }
  }

  &__sub {
    width: 100%;
    display: flex;
    align-items: flex-start;
    gap: 10px;
  }

  &__subtitle {
    width: 283px;
    font-family: "Inter", sans-serif;
    font-weight: 400;
    font-size: var(--landing-fs-base);
    color: #000;
    text-transform: uppercase;
    line-height: normal;
    margin: 0;
  }

  &__cta-wrap {
    flex: 1 0 0;
    min-width: 0;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
  }

  &__cta {
    background: var(--landing-green-light-1);
    border-radius: var(--landing-r-pill);
    padding: 10px 20px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    border: none;
    cursor: pointer;
    font-family: "Inter", sans-serif;
    font-weight: 700;
    font-size: var(--landing-fs-base);
    color: var(--landing-green-deep);
    transition: transform 0.3s ease;
    position: relative;
    overflow: hidden;

    img {
      width: 24px;
      height: 24px;
      display: block;
    }

    &:hover {
      transform: translateY(-2px);
    }
  }
}
</style>
