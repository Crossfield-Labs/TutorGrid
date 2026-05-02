<script setup lang="ts">
import { FIGMA_ASSETS as A } from "../assets";

// 4 张窄卡（与 1 张宽卡一起共 5 张，滚动节奏更自然）
const narrowCards = [
  { title: "Forest gardens", outlined: false },
  { title: "Forest gardens", outlined: true },
  { title: "Wildlife shelter", outlined: false },
  { title: "Clean rivers", outlined: true },
];
</script>

<template>
  <section class="landing-projects" data-node-id="0:234">
    <!-- 卡 1：Cleaning up the Danube（宽卡，灰底，左文右图） -->
    <div class="landing-projects__card landing-projects__card--wide" data-node-id="0:235">
      <div class="landing-projects__text">
        <h3 class="landing-projects__title">Cleaning up the Danube</h3>
        <p class="landing-projects__desc">
          Our team is actively working to clean up the Danube River from
          pollution in order to restore its natural beauty.
        </p>
        <div class="landing-projects__bottom">
          <span class="landing-projects__more-text">View more</span>
          <button v-ripple class="landing-circle-btn" data-node-id="0:241">
            <img :src="A.arrowDown" alt="" />
          </button>
          <img class="landing-projects__sm-arrow" :src="A.iconArrowRight" alt="" />
        </div>
      </div>
      <div class="landing-projects__image">
        <img :src="A.projectImg1" alt="" />
      </div>
    </div>

    <!-- 卡 2-5：4 张窄卡（v-for） -->
    <div
      v-for="(card, i) in narrowCards"
      :key="i"
      class="landing-projects__card landing-projects__card--narrow"
    >
      <div class="landing-projects__col">
        <div class="landing-projects__chip">
          <span>{{ card.title }}</span>
        </div>
        <div class="landing-projects__more-row">
          <img class="landing-projects__leaf" :src="A.projectLeaf" alt="" />
          <span>View more</span>
        </div>
      </div>
      <button
        v-ripple
        class="landing-circle-btn"
        :class="{ outlined: card.outlined }"
      >
        <img :src="A.arrowDown" alt="" />
      </button>
    </div>
  </section>
</template>

<style lang="scss" scoped>
@use "../styles/landing.scss";

.landing-projects {
  width: 2040px; // 1 宽卡(600) + 4 窄卡(340*4) + 5 间距(20*4)
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 20px;

  &__card {
    height: 407px;
    border-radius: var(--landing-r-pill);
    flex-shrink: 0;
    display: flex;
  }

  &__card--wide {
    width: 600px;
    background: var(--landing-gray-cell);
    padding: 40px;
    align-items: center;
    gap: 60px;
  }

  &__card--narrow {
    width: 340px;
    background: var(--landing-green-light-3);
    padding: 40px;
    align-items: flex-end;
    justify-content: flex-end;
    gap: 20px;
    overflow: hidden;
    position: relative;
  }

  &__text {
    flex: 1 0 0;
    min-width: 0;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
    padding-top: 20px;
  }

  &__title {
    width: 100%;
    font-family: "Inter", sans-serif;
    font-weight: 700;
    font-size: var(--landing-fs-card);
    color: #000;
    line-height: normal;
    text-transform: uppercase;
    margin: 0;
  }

  &__desc {
    flex: 1 0 0;
    min-height: 0;
    width: 100%;
    font-family: "Inter", sans-serif;
    font-weight: 400;
    font-size: var(--landing-fs-base);
    color: #000;
    line-height: 1.8;
    text-transform: uppercase;
    margin: 0;
  }

  &__bottom {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 10px;
  }

  &__more-text {
    flex: 1 0 0;
    min-width: 0;
    font-family: "Inter", sans-serif;
    font-weight: 400;
    font-size: var(--landing-fs-base);
    color: #000;
    text-transform: uppercase;
    line-height: normal;
  }

  &__sm-arrow {
    width: 16px;
    height: 16px;
    display: block;
  }

  &__image {
    width: 232px;
    height: 100%;
    border-radius: var(--landing-r-img);
    overflow: hidden;
    background: #fff;
    flex-shrink: 0;

    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }
  }

  &__col {
    flex: 1 0 0;
    min-width: 0;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    align-items: flex-start;
    position: relative;
  }

  &__chip {
    background: #fff;
    border-radius: 10px;
    padding: 10px;
    display: inline-flex;
    align-items: center;
    justify-content: center;

    span {
      font-family: "Inter", sans-serif;
      font-weight: 700;
      font-size: var(--landing-fs-card);
      color: #000;
      line-height: 1;
      text-transform: uppercase;
      white-space: nowrap;
    }
  }

  &__more-row {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    position: relative;

    span {
      font-family: "Inter", sans-serif;
      font-weight: 400;
      font-size: var(--landing-fs-base);
      color: #000;
      text-transform: uppercase;
      line-height: normal;
      white-space: nowrap;
    }
  }

  &__leaf {
    position: absolute;
    width: 179px;
    height: 194px;
    left: -74px;
    top: -110px;
    pointer-events: none;
  }
}
</style>
