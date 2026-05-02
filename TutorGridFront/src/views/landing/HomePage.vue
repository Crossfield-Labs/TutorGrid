<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { fadeInUp } from "./composables/useLandingAnimations";
import { FIGMA_ASSETS as A } from "./assets";

import LandingNav from "./components/LandingNav.vue";
import LandingHero from "./components/LandingHero.vue";
import LandingBento from "./components/LandingBento.vue";
import LandingMarquee from "./components/LandingMarquee.vue";
import LandingMission from "./components/LandingMission.vue";
import LandingProjects from "./components/LandingProjects.vue";
import LandingBrand from "./components/LandingBrand.vue";
import LandingInvolve from "./components/LandingInvolve.vue";
import LandingGallery from "./components/LandingGallery.vue";

const sections = ref<HTMLElement[]>([]);
const projectsWrap = ref<HTMLElement | null>(null);

// 鼠标按住拖拽横向滚动（项目卡那行）
function setupDragScroll(el: HTMLElement) {
  let isDown = false;
  let startX = 0;
  let scrollLeft = 0;
  const onDown = (e: MouseEvent) => {
    isDown = true;
    startX = e.pageX - el.offsetLeft;
    scrollLeft = el.scrollLeft;
  };
  const onLeave = () => (isDown = false);
  const onUp = () => (isDown = false);
  const onMove = (e: MouseEvent) => {
    if (!isDown) return;
    e.preventDefault();
    const x = e.pageX - el.offsetLeft;
    el.scrollLeft = scrollLeft - (x - startX) * 1.2;
  };
  el.addEventListener("mousedown", onDown);
  el.addEventListener("mouseleave", onLeave);
  el.addEventListener("mouseup", onUp);
  el.addEventListener("mousemove", onMove);
  return () => {
    el.removeEventListener("mousedown", onDown);
    el.removeEventListener("mouseleave", onLeave);
    el.removeEventListener("mouseup", onUp);
    el.removeEventListener("mousemove", onMove);
  };
}

let cleanupDrag: (() => void) | null = null;

onMounted(() => {
  // 各 section 入场（柔和上移，不打断 marquee/hero 的循环动画）
  sections.value.forEach((el, i) => {
    if (el) fadeInUp(el, { y: 24, duration: 0.95, delay: i === 0 ? 0.1 : 0 });
  });
  // 项目区拖拽滚动；初始 scrollLeft=0 让第一张卡左边和上方文字 col 对齐
  if (projectsWrap.value) {
    cleanupDrag = setupDragScroll(projectsWrap.value);
  }
  // 图片加载完后强制重算所有 ScrollTrigger 位置（避免初始算错导致触发延迟）
  const onLoad = () => ScrollTrigger.refresh();
  window.addEventListener("load", onLoad);
  // 字体加载也会改变布局
  if ((document as any).fonts?.ready) {
    (document as any).fonts.ready.then(() => ScrollTrigger.refresh());
  }
  // 兜底
  setTimeout(() => ScrollTrigger.refresh(), 500);
});

onUnmounted(() => {
  cleanupDrag?.();
});
</script>

<template>
  <div class="landing-page" data-node-id="0:76" data-name="Tea-Landing-Page">
    <!-- 顶部 Nav -->
    <div
      class="landing-page__col"
      :ref="(el) => { if (el) sections[0] = el as HTMLElement; }"
    >
      <LandingNav />

      <!-- Hero -->
      <LandingHero />

      <!-- Bento -->
      <LandingBento />
    </div>

    <!-- ④ 跑马灯（注意：跑马灯本身全宽，不在 1020px col 里）-->
    <div
      class="landing-page__full"
      :ref="(el) => { if (el) sections[1] = el as HTMLElement; }"
    >
      <LandingMarquee />
    </div>

    <!-- ⑤ Mission + ⑥ Projects -->
    <div
      class="landing-page__col"
      :ref="(el) => { if (el) sections[2] = el as HTMLElement; }"
    >
      <LandingMission />
    </div>

    <div
      class="landing-page__projects-wrap"
      :ref="(el) => { if (el) { sections[3] = el as HTMLElement; projectsWrap = el as HTMLElement; } }"
    >
      <LandingProjects />
    </div>

    <!-- ⑦ Brand 大字 -->
    <div :ref="(el) => { if (el) sections[4] = el as HTMLElement; }">
      <LandingBrand />
    </div>

    <!-- ⑧ Get Involved -->
    <div :ref="(el) => { if (el) sections[5] = el as HTMLElement; }">
      <LandingInvolve />
    </div>

    <!-- ⑨ Gallery -->
    <div :ref="(el) => { if (el) sections[6] = el as HTMLElement; }">
      <LandingGallery />
    </div>

    <!-- 大背景圆：1.4 倍视口宽，绝对定位贴页面底，横向自然超出视口 -->
    <div
      class="landing-page__bg-circle"
      :style="{ backgroundImage: `url(${A.bgDeco})` }"
    ></div>
  </div>
</template>

<style lang="scss">
// 引入 landing token（全局，让所有子组件都能用 var(--landing-*)）
@use "./styles/landing.scss";
</style>

<style lang="scss" scoped>
.landing-page {
  background: var(--landing-bg);
  width: 100%;
  min-height: 100vh;
  // 底部 padding 必须为 0，让 Gallery section 贴页面底，
  // 大圆下半圆才能"占满最下面屏幕"
  padding: 40px 0 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 86px;
  position: relative;
  overflow: clip; // 双向 clip：横向藏圆超出，纵向藏圆下半部，且不创建滚动容器
  font-family: "Inter", sans-serif;

  // 所有内容默认在背景圆上方
  & > *:not(.landing-page__bg-circle) {
    position: relative;
    z-index: 1;
  }

  // 大背景圆：完整圆形，1.4 倍视口宽，超出视口两侧由 overflow:clip 自然消去；
  // 圆心略低于页面底，让大半个圆浮在 Gallery 区域作背景
  &__bg-circle {
    position: absolute;
    width: 100vw;          // ← ① 圆直径（1.4× 视口）
    aspect-ratio: 1 / 1;   // 真·正圆
    left: 50%;
    bottom: 0;
    transform: translate(-50%, 66%);  // ← ② 圆心下沉 30% 高度（露出 70% 圆）
    background-size: contain;
    background-repeat: no-repeat;
    background-position: center;
    pointer-events: none;
    z-index: 0;            // 在内容下方
    opacity: 0.4;          // ← ③ 透明度
  }

  // 主栏：响应式宽度，最大 1280，最小留 4% 视口边距
  &__col {
    width: min(1280px, 92vw);
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 20px;
    position: relative;
    z-index: 1;
  }

  // 全宽容器（marquee 用）
  &__full {
    width: 100%;
    display: flex;
    justify-content: center;
    position: relative;
    z-index: 1;
  }

  // 项目区：横向可滚动，初始第一张卡左边和上方文字 col 对齐
  &__projects-wrap {
    width: 100%;
    overflow-x: auto;
    overflow-y: hidden;
    // padding-left 等于 col 的自然左边距 → 卡 1 左边与 Mission 文字左边对齐
    // 公式：(视口宽 - col宽) / 2，col宽 = min(1280, 92vw)
    padding-left: max(4vw, calc((100vw - min(1280px, 92vw)) / 2));
    padding-right: 4vw;
    position: relative;
    z-index: 1;
    cursor: grab;
    scrollbar-width: none;
    &::-webkit-scrollbar {
      display: none;
    }
    &:active {
      cursor: grabbing;
    }
  }
}
</style>
