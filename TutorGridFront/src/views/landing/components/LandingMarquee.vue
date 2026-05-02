<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { gsap } from "gsap";
import { FIGMA_ASSETS as A } from "../assets";
import { marqueeLoop } from "../composables/useLandingAnimations";

// 一组重复单元（4 对：sun_line + 文字 + sun_fill + 文字）
const repeatUnit = [
  { icon: A.iconSunLine2, text: "GrEen The PlaneT" },
  { icon: A.iconSunFill, text: "GrEen The PlaneT" },
  { icon: A.iconSunLine2, text: "GrEen The PlaneT" },
  { icon: A.iconSunFill, text: "GrEen The PlaneT" },
];

const trackRef = ref<HTMLElement | null>(null);
let tween: gsap.core.Tween | null = null;

onMounted(() => {
  if (trackRef.value) {
    tween = marqueeLoop(trackRef.value, 40);
  }
});

onUnmounted(() => {
  tween?.kill();
});
</script>

<template>
  <div class="landing-marquee" data-node-id="0:182">
    <div class="landing-marquee__track" ref="trackRef">
      <!-- 渲染两份内容实现无缝循环 -->
      <template v-for="n in 2" :key="n">
        <div v-for="(item, i) in repeatUnit" :key="`${n}-${i}`" class="landing-marquee__item">
          <img :src="item.icon" alt="" />
          <p>{{ item.text }}</p>
        </div>
      </template>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.landing-marquee {
  width: 100%;
  background: var(--landing-green-light-1);
  padding: 10px 20px;
  overflow: hidden;
  position: relative;

  &__track {
    display: inline-flex;
    align-items: center;
    gap: 20px;
    white-space: nowrap;
    will-change: transform;
  }

  &__item {
    display: inline-flex;
    align-items: center;
    gap: 20px;
    flex-shrink: 0;

    img {
      width: 24px;
      height: 24px;
      display: block;
    }

    p {
      font-family: "Inter", sans-serif;
      font-weight: 700;
      font-size: var(--landing-fs-base);
      color: var(--landing-green-deep-2);
      text-transform: uppercase;
      text-align: center;
      line-height: normal;
      margin: 0;
      white-space: nowrap;
    }
  }
}
</style>
