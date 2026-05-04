<script setup lang="ts">
import { FIGMA_ASSETS as A } from "../assets";
</script>

<template>
  <div class="landing-nav" data-node-id="0:79">
    <p class="landing-nav__brand" data-node-id="0:80">智格生境</p>

    <div class="landing-nav__menu">
      <div class="landing-nav__pill" data-node-id="0:82">
        <div class="landing-nav__icon-bg">
          <div class="landing-nav__icon">
            <img :src="A.iconFan" alt="" />
          </div>
        </div>
        <p>核心功能</p>
      </div>

      <div class="landing-nav__pill" data-node-id="0:89">
        <div class="landing-nav__icon-bg">
          <div class="landing-nav__icon">
            <img :src="A.iconMail" alt="" />
          </div>
        </div>
        <p>技术架构</p>
      </div>

      <div class="landing-nav__pill" data-node-id="0:96">
        <div class="landing-nav__icon-bg">
          <div class="landing-nav__icon">
            <img :src="A.iconChart" alt="" />
          </div>
        </div>
        <p>开发团队</p>
      </div>
    </div>

    <v-btn
      class="landing-nav__contact"
      color="black"
      variant="flat"
      data-node-id="0:103"
      href="https://github.com/Crossfield-Labs/TutorGrid"
      target="_blank"
      prepend-icon="mdi-github"
    >
      <span>Github</span>
    </v-btn>
  </div>
</template>

<style lang="scss" scoped>
.landing-nav {
  display: flex;
  align-items: center;
  gap: 20px;
  width: 100%;

  &__brand {
    font-family: "Inter", sans-serif;
    font-weight: 700;
    font-size: 16px;
    color: #000;
    width: 115px;
    line-height: normal;
  }

  &__menu {
    flex: 1 0 0;
    min-width: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 20px;
  }

  &__pill {
    display: flex;
    align-items: center;
    gap: 4px;
    background: var(--landing-gray-pill);
    border-radius: var(--landing-r-pill);
    padding: 2px 10px 2px 2px;

    p {
      font-family: "Inter", sans-serif;
      font-weight: 400;
      font-size: var(--landing-fs-base);
      color: #000;
      white-space: nowrap;
      line-height: normal;
    }
  }

  &__icon-bg {
    background: #ffffff;
    border-radius: var(--landing-r-pill);
    padding: 4px;
    display: flex;
    align-items: center;
  }

  &__icon {
    width: 24px;
    height: 24px;
    border-radius: 10px;
    overflow: hidden;
    img {
      width: 100%;
      height: 100%;
      display: block;
    }
  }

  &__contact {
    font-family: "Inter", sans-serif;
    font-weight: 400;
    font-size: var(--landing-fs-base);
    text-transform: none;
    letter-spacing: 0;
    border-radius: var(--landing-r-pill);
    padding: 2px 20px;
    height: auto !important;
    min-width: 0 !important;
    align-self: stretch;
  }
}
</style>
