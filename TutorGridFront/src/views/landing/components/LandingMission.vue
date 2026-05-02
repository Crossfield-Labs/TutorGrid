<script setup lang="ts">
import { FIGMA_ASSETS as A } from "../assets";
</script>

<template>
  <section class="landing-mission" data-node-id="0:213">
    <!-- 上半区：左短文 + 右大标题 + CTA -->
    <div class="landing-mission__row" data-node-id="0:214">
      <p class="landing-mission__lead">
        The GreenWorld has carried out many successful projects for
        reforestation and blodiversity conservation.
      </p>
      <div class="landing-mission__right">
        <h2 class="landing-mission__title">
          We strive to protect nature for future generations.
        </h2>
        <div class="landing-mission__cta-group">
          <button class="landing-mission__cta" data-node-id="0:219" v-ripple>
            <span>About Us</span>
          </button>
          <div class="landing-mission__more">
            <span>View more</span>
            <img :src="A.iconArrowRight" alt="" />
          </div>
        </div>
      </div>
    </div>

    <!-- 下半区："Our Projects" 标 + 大标题（含 environment 高亮胶囊） -->
    <div class="landing-mission__projects-head" data-node-id="0:227">
      <div class="landing-mission__chip" data-node-id="0:228">
        <span>Our Projects</span>
      </div>
      <div class="landing-mission__heading-wrap" data-node-id="0:230">
        <p class="landing-mission__heading">
          <span>We hold various events, campaigns and raise funds for the implementation of projects to preserve the&nbsp;</span>
          <span class="landing-mission__env-pill" data-node-id="0:232">environment</span>
        </p>
      </div>
    </div>
  </section>
</template>

<style lang="scss" scoped>
.landing-mission {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 50px;
  align-items: flex-start;

  &__row {
    width: 100%;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 86px;
  }

  &__lead {
    flex: 1 0 0;
    min-width: 0;
    font-family: "Inter", sans-serif;
    font-weight: 400;
    font-size: var(--landing-fs-base);
    color: #000;
    line-height: 1.8;
    text-transform: uppercase;
    margin: 0;
  }

  &__right {
    width: 52%;
    max-width: 640px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 20px;
    align-items: flex-start;
  }

  &__title {
    width: 100%;
    font-family: "Inter", sans-serif;
    font-weight: 700;
    font-size: var(--landing-fs-h2);
    color: #000;
    line-height: 1.1;
    text-transform: uppercase;
    margin: 0;
  }

  &__cta-group {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  &__cta {
    background: var(--landing-green-light-1);
    border: none;
    border-radius: var(--landing-r-pill);
    padding: 10px 20px;
    font-family: "Inter", sans-serif;
    font-weight: 700;
    font-size: var(--landing-fs-nav);
    color: var(--landing-green-deep);
    cursor: pointer;
    line-height: normal;
    position: relative;
    overflow: hidden;
    transition: transform 0.3s ease;

    &:hover {
      transform: translateY(-2px);
    }
  }

  &__more {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-family: "Inter", sans-serif;
    font-weight: 400;
    font-size: var(--landing-fs-base);
    color: #000;
    text-transform: uppercase;

    img {
      width: 16px;
      height: 16px;
      display: block;
    }
  }

  &__projects-head {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 20px;
    align-items: flex-start;
  }

  &__chip {
    background: #fff;
    border: 1px solid rgba(0, 0, 0, 0.8);
    border-radius: var(--landing-r-pill);
    padding: 10px 20px;
    display: inline-flex;
    align-items: center;

    span {
      font-family: "Inter", sans-serif;
      font-weight: 700;
      font-size: var(--landing-fs-nav);
      color: var(--landing-green-deep);
      line-height: normal;
      white-space: nowrap;
    }
  }

  &__heading-wrap {
    width: 100%;
    padding-right: 110px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    align-items: flex-start;
  }

  &__heading {
    width: 100%;
    font-family: "Inter", sans-serif;
    font-weight: 700;
    font-size: var(--landing-fs-h2);
    color: #000;
    line-height: 1.4;
    text-transform: uppercase;
    margin: 0;
  }

  // 嵌入文本流的高亮胶囊
  &__env-pill {
    background: var(--landing-green-light-1);
    border-radius: var(--landing-r-pill-lg);
    padding: 2px 14px;
    display: inline-block;
    line-height: 1.1;
    white-space: nowrap;
    vertical-align: middle;
    margin-left: 4px;
  }
}
</style>
