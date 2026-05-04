<script setup lang="ts">
import { ref } from "vue";
import { FIGMA_ASSETS as A } from "../assets";

// 第二项（"share information"）默认展开 — 复刻设计稿状态
const expanded = ref<number>(1);

const items = [
  {
    title: "Vue 3 + Vuetify 3 + Electron 桌面端",
    desc: "基于 TypeScript 全栈开发，TipTap 2 富文本编辑器，Pinia 状态管理，本地化部署。",
  },
  {
    title: "LangGraph 多智能体编排引擎",
    desc: "LangGraph v1.1 驱动的编排图，支持 Planning → Tools → Verify → Finalize 流程，Worker/CLI 委派执行，中断恢复。",
  },
  {
    title: "RAG + Tavily 双源检索增强",
    desc: "EnsembleRetriever（BM25 + FAISS）融合检索，RRF 排序 + Rerank 精排，Tavily 联网搜索补充最新知识。",
  },
  {
    title: "DeepSeek-V4-Pro 大模型驱动",
    desc: "1.6T 参数 / 49B 激活，100 万 Token 上下文窗口，国产合规，高性价比。",
  },
];

function toggle(i: number) {
  expanded.value = expanded.value === i ? -1 : i;
}
</script>

<template>
  <section class="landing-involve" data-node-id="0:283">
    <!-- 上半区：左大标题 "Get Involved↗" + 右说明文 -->
    <div class="landing-involve__head" data-node-id="0:284">
      <div class="landing-involve__head-left" data-node-id="0:285">
        <h2>技术栈</h2>
        <button class="landing-circle-btn" style="padding: 0">
          <img :src="A.arrowDown" alt="" style="width: 32px; height: 32px" />
        </button>
      </div>
      <p class="landing-involve__head-right" data-node-id="0:290">
        智格生境采用前后端分离架构，前端 Electron 桌面应用，
        后端 FastAPI 提供 Chat SSE / 编排 WebSocket / REST 三通道服务。
      </p>
    </div>

    <!-- 折叠列表：4 项 -->
    <div class="landing-involve__list" data-node-id="0:291">
      <div
        v-for="(item, i) in items"
        :key="i"
        class="landing-involve__cell"
        :class="{ 'is-expanded': expanded === i }"
        @click="toggle(i)"
        v-ripple
      >
        <div class="landing-involve__cell-text">
          <p class="landing-involve__cell-title">{{ item.title }}</p>
          <p v-if="expanded === i && item.desc" class="landing-involve__cell-desc">
            {{ item.desc }}
          </p>
        </div>
        <div class="landing-circle-btn outlined">
          <img :src="expanded === i ? A.arrowUp : A.arrowDown" alt="" />
        </div>
      </div>
    </div>
  </section>
</template>

<style lang="scss" scoped>
@use "../styles/landing.scss";

.landing-involve {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 30px;
  align-items: flex-start;

  &__head {
    width: 100%;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 86px;
  }

  &__head-left {
    width: 52%;
    max-width: 640px;
    flex-shrink: 0;
    display: flex;
    align-items: flex-start;
    gap: 4px;

    h2 {
      font-family: "Inter", sans-serif;
      font-weight: 700;
      font-size: var(--landing-fs-h2);
      color: #000;
      line-height: 1.1;
      text-transform: uppercase;
      white-space: nowrap;
      margin: 0;
    }

    .landing-circle-btn {
      width: 32px;
      height: 32px;
      padding: 0;
      border-radius: 0; // 这里其实是 32x32 的 group icon，不是圆按钮
      background: transparent;
    }
  }

  &__head-right {
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

  &__list {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  &__cell {
    width: 100%;
    background: var(--landing-gray-cell);
    border-radius: var(--landing-r-pill);
    padding: 20px 40px;
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    transition: background-color 0.3s ease;
    position: relative;
    overflow: hidden;

    &.is-expanded {
      background: var(--landing-green-light-3);
    }
  }

  &__cell-text {
    flex: 1 0 0;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
    align-items: flex-start;
    text-transform: uppercase;
    color: #000;
  }

  &__cell-title {
    width: 100%;
    font-family: "Inter", sans-serif;
    font-weight: 700;
    font-size: var(--landing-fs-card);
    line-height: normal;
    margin: 0;
  }

  &__cell-desc {
    width: 100%;
    font-family: "Inter", sans-serif;
    font-weight: 400;
    font-size: var(--landing-fs-base);
    line-height: 1.8;
    margin: 0;
  }
}
</style>
