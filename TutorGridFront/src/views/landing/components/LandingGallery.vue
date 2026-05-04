<script setup lang="ts">
import { FIGMA_ASSETS as A } from "../assets";

const socialLinks = [
  
];
</script>

<template>
  <section class="landing-gallery" data-node-id="0:307">
    <!-- 上：Our Gallery 标 + 大标题 -->
    <div class="landing-gallery__head" data-node-id="0:308">
      <div class="landing-gallery__chip" data-node-id="0:309">
        <span>关于我们</span>
      </div>
      <h2 class="landing-gallery__title" data-node-id="0:311">
        Concrete.AI · 第19届中国大学生计算机设计大赛
      </h2>
    </div>

    <!-- 中：椭圆图 + 中央 SEE ALL PHOTOS -->
    <div class="landing-gallery__oval" data-node-id="0:312">
      <div
        class="landing-gallery__oval-bg"
        :style="{ backgroundImage: `url(${A.galleryOval})` }"
      ></div>
      <div class="landing-gallery__see-all" data-node-id="0:313" v-ripple>
        <p>了解<br />团队</p>
      </div>
    </div>

    <!-- 下：social info -->
    <div class="landing-gallery__social" data-node-id="0:33">
      <div
        v-for="(item, i) in socialLinks"
        :key="i"
        class="landing-gallery__social-item"
      >
        <div class="landing-gallery__social-icon">
          <img :src="item.icon" alt="" />
        </div>
        <p>{{ item.name }}</p>
      </div>
    </div>
  </section>
</template>

<style lang="scss" scoped>
.landing-gallery {
  width: min(1280px, 92vw);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 80px;
  position: relative;

  &__head {
    width: 640px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;
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

  &__title {
    width: 100%;
    font-family: "Inter", sans-serif;
    font-weight: 700;
    font-size: var(--landing-fs-h2);
    color: #000;
    text-align: center;
    line-height: 1.2;
    text-transform: uppercase;
    margin: 0;
  }

  &__oval {
    position: relative;
    width: 580px;
    height: 300px;
    border-radius: var(--landing-r-oval);
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--landing-gray-mute);
  }

  &__oval-bg {
    position: absolute;
    inset: 0;
    background-size: cover;
    background-position: center;
    border-radius: var(--landing-r-oval);
  }

  &__see-all {
    position: relative;
    z-index: 1;
    width: 130px;
    height: 130px;
    background: #fff;
    border-radius: 200px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: transform 0.3s ease;
    overflow: hidden;

    &:hover {
      transform: scale(1.05);
    }

    p {
      font-family: "Inter", sans-serif;
      font-weight: 700;
      font-size: var(--landing-fs-nav);
      color: #000;
      line-height: normal;
      text-align: center;
      margin: 0;
      white-space: pre;
    }
  }

  &__social {
    display: flex;
    align-items: flex-start;
    gap: 20px;
  }

  &__social-item {
    display: flex;
    align-items: center;
    gap: 5px;

    p {
      font-family: "Alibaba PuHuiTi", "PingFang SC", "Microsoft YaHei",
        sans-serif;
      font-weight: 400;
      font-size: 12px;
      color: #000;
      line-height: normal;
      margin: 0;
      white-space: nowrap;
    }
  }

  &__social-icon {
    width: 18px;
    height: 18px;
    display: flex;
    align-items: center;
    justify-content: center;

    img {
      width: 100%;
      height: 100%;
      display: block;
    }
  }
}
</style>
