<script setup lang="ts">
import { FIGMA_ASSETS as A } from "../assets";
</script>

<template>
  <section class="landing-bento" data-node-id="0:147">
    <!-- 卡 1：左侧小图 -->
    <div class="landing-bento__img-card landing-bento__card-1" data-node-id="0:148">
      <img :src="A.bentoImg1" alt="" />
    </div>

    <!-- 卡 2：双层文字卡（灰 + 浅绿） -->
    <div class="landing-bento__stack" data-node-id="0:149">
      <div class="landing-bento__stack-row gray" data-node-id="0:150">
        <p class="landing-bento__stack-title">Hyper 文档共做</p>
        <p class="landing-bento__stack-desc">
          你和 AI 都是一等作者，写一段、补一段，文档即学习轨迹
        </p>
      </div>
      <div class="landing-bento__stack-row green" data-node-id="0:153">
        <p class="landing-bento__stack-title">多智能体编排引擎</p>
        <p class="landing-bento__stack-desc">
          /task 一句话触发，LangGraph 自动规划 → 执行 → 汇总
        </p>
      </div>
    </div>

    <!-- 卡 3：篝火图 + 顶部圆按钮 + 底部白底卡 -->
    <div class="landing-bento__photo landing-bento__photo--narrow" data-node-id="0:156">
      <div class="landing-bento__overlay" :style="{ backgroundImage: `url(${A.bentoImg2})` }"></div>
      <div class="landing-bento__photo-icon-pill" data-node-id="0:157">
        <img :src="A.iconCampfire" alt="" />
      </div>
      <div class="landing-bento__photo-bottom-cta" data-node-id="0:162" v-ripple>
        <p>磁贴式自适应工具箱</p>
      </div>
    </div>

    <!-- 卡 4：大图 + 顶部双 Tag + 底部 Donate -->
    <div class="landing-bento__photo landing-bento__photo--wide" data-node-id="0:164">
      <div class="landing-bento__overlay" :style="{ backgroundImage: `url(${A.bentoImg3})` }"></div>
      <div class="landing-bento__photo-tags" data-node-id="0:165">
        <div class="landing-bento__tag" data-node-id="0:166"><p>RAG</p></div>
        <div class="landing-bento__tag" data-node-id="0:168"><p>联网搜索</p></div>
      </div>
      <div class="landing-bento__photo-bottom-row" data-node-id="0:170" v-ripple>
        <p>知识库检索 + Tavily 联网双源问答</p>
        <img :src="A.iconArrowRightUpCircle" alt="" />
      </div>
    </div>

    <!-- 卡 5：浅绿小卡 -->
    <div class="landing-bento__small-cta" data-node-id="0:176" v-ripple>
      <img :src="A.iconArrowRightUpCircle" alt="" />
      <p>DeepSeek-V4-Pro 驱动</p>
    </div>
  </section>
</template>

<style lang="scss" scoped>
.landing-bento {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;

  // 卡 1：固定 154x161 圆角图
  &__img-card {
    width: 154px;
    height: 161px;
    border-radius: var(--landing-r-pill);
    overflow: hidden;
    background: var(--landing-gray-img);
    flex-shrink: 0;

    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }
  }

  // 卡 2：双层文字 stack（自适应宽）
  &__stack {
    flex: 1 0 0;
    min-width: 0;
    background: var(--landing-gray-cell);
    border-radius: var(--landing-r-pill);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }

  &__stack-row {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: 20px;
    text-align: center;
    text-transform: uppercase;

    &.gray {
      background: var(--landing-gray-cell);
    }
    &.green {
      background: var(--landing-green-light-1);
      border-radius: var(--landing-r-pill);
    }
  }

  &__stack-title {
    width: 100%;
    font-family: "Inter", sans-serif;
    font-weight: 700;
    font-size: var(--landing-fs-nav);
    color: #000;
    line-height: normal;
    margin: 0;
  }

  &__stack-desc {
    width: 100%;
    font-family: "Inter", sans-serif;
    font-weight: 400;
    font-size: var(--landing-fs-base);
    color: #000;
    line-height: normal;
    margin: 0;
  }

  // 共用：图片背景卡
  &__photo {
    position: relative;
    border-radius: var(--landing-r-pill);
    overflow: hidden;
    flex-shrink: 0;
    padding: 20px;
    display: flex;
    flex-direction: column;
    background: var(--landing-gray-img);
  }
  &__photo--narrow {
    width: 264px;
    height: 407px;
    align-items: center;
    justify-content: space-between;
  }
  &__photo--wide {
    flex: 1 0 0;
    min-width: 0;
    height: 345px;
    justify-content: space-between;
    align-items: flex-start;
  }

  &__overlay {
    position: absolute;
    inset: 0;
    background-size: cover;
    background-position: center;
    border-radius: var(--landing-r-pill);
    pointer-events: none;
    z-index: 0;
  }

  &__photo > *:not(.landing-bento__overlay) {
    position: relative;
    z-index: 1;
  }

  &__photo-icon-pill {
    background: #fff;
    border-radius: var(--landing-r-pill);
    padding: 20px;
    display: inline-flex;
    align-items: center;

    img {
      width: 24px;
      height: 24px;
      display: block;
    }
  }

  &__photo-bottom-cta {
    width: 100%;
    background: rgba(255, 255, 255, 0.8);
    border-radius: var(--landing-r-pill);
    padding: 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    cursor: pointer;
    overflow: hidden;

    p {
      width: 100%;
      font-family: "Inter", sans-serif;
      font-weight: 700;
      font-size: var(--landing-fs-nav);
      color: #000;
      text-align: center;
      text-transform: uppercase;
      line-height: normal;
      margin: 0;
    }
  }

  &__photo-tags {
    display: flex;
    align-items: flex-start;
    gap: 10px;
  }

  &__tag {
    border: 2px solid #fff;
    border-radius: var(--landing-r-pill);
    padding: 10px;
    display: flex;
    flex-direction: column;
    align-items: center;

    p {
      font-family: "Inter", sans-serif;
      font-weight: 700;
      font-size: var(--landing-fs-nav);
      color: #fff;
      text-align: center;
      text-transform: uppercase;
      line-height: normal;
      margin: 0;
      white-space: nowrap;
    }
  }

  &__photo-bottom-row {
    width: 100%;
    background: rgba(255, 255, 255, 0.8);
    border-radius: var(--landing-r-pill);
    padding: 20px;
    display: flex;
    align-items: flex-end;
    justify-content: flex-end;
    gap: 4px;
    cursor: pointer;
    overflow: hidden;

    p {
      flex: 1 0 0;
      min-width: 0;
      font-family: "Inter", sans-serif;
      font-weight: 700;
      font-size: var(--landing-fs-nav);
      color: #000;
      text-transform: uppercase;
      line-height: normal;
      margin: 0;
    }

    img {
      width: 24px;
      height: 24px;
      display: block;
    }
  }

  // 卡 5：右侧浅绿小 CTA
  &__small-cta {
    width: 154px;
    height: 150px;
    background: var(--landing-green-light-3);
    border-radius: var(--landing-r-pill);
    padding: 30px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    flex-shrink: 0;
    cursor: pointer;
    position: relative;
    overflow: hidden;

    img {
      width: 24px;
      height: 24px;
      display: block;
    }

    p {
      width: 150px;
      font-family: "Inter", sans-serif;
      font-weight: 400;
      font-size: var(--landing-fs-base);
      color: #000;
      text-align: center;
      text-transform: uppercase;
      line-height: normal;
      margin: 0;
    }
  }
}
</style>
