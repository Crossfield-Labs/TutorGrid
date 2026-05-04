<script setup lang="ts">
import { FIGMA_ASSETS as A } from "../assets";
</script>

<template>
  <section class="landing-brand" data-node-id="0:276">
    <p class="landing-brand__word landing-brand__word--outline" data-node-id="0:277">
      TUTOR
    </p>

    <div class="landing-brand__circle" data-node-id="0:278">
      <img class="landing-brand__ring landing-brand__ring--outer" :src="A.brandRing1" alt="" />
      <img class="landing-brand__ring landing-brand__ring--mid" :src="A.brandRing2" alt="" />
      <img class="landing-brand__ring landing-brand__ring--inner" :src="A.brandLeaf" alt="" />
    </div>

    <p class="landing-brand__word landing-brand__word--solid" data-node-id="0:282">
      Grid
    </p>
  </section>
</template>

<style lang="scss" scoped>
.landing-brand {
  display: flex;
  align-items: center;
  gap: 60px;

  &__word {
    font-family: "Inter", sans-serif;
    font-weight: 900;
    font-size: var(--landing-fs-mega);
    letter-spacing: 16px;
    text-transform: uppercase;
    line-height: normal;
    margin: 0;
    white-space: nowrap;

    &--outline {
      // Figma 中是 transparent 文字色（描边/渐隐效果）
      color: transparent;
      -webkit-text-stroke: 1.5px #000;
    }

    &--solid {
      color: #000;
    }
  }

  &__circle {
    position: relative;
    width: 254px;
    height: 254px;

    .landing-brand__ring {
      position: absolute;
      display: block;
    }

    &--outer {
      // 占位
    }
  }

  &__ring {
    &--outer {
      top: 0;
      left: 0;
      width: 254px;
      height: 254px;
    }
    &--mid {
      top: 0;
      left: 0;
      width: 254px;
      height: 254px;
    }
    &--inner {
      top: 13px;
      left: 13px;
      width: 228px;
      height: 228px;
    }
  }
}
</style>
