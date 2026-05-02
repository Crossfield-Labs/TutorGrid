// 克制的 GSAP 动画集合，用于 landing 页
// 原则：subtle, not flashy — 短距离位移、线性匀速、轻微缓出

import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

/**
 * 滚动进入视口时淡入上移（默认 24px、0.95s）
 * 用 onEnter + start "top bottom" 确保元素一进视口就触发，
 * 避免大 section 顶部过晚到达 trigger 点导致白屏
 */
export function fadeInUp(
  el: HTMLElement,
  opts: { delay?: number; y?: number; duration?: number } = {}
) {
  const { delay = 0, y = 24, duration = 0.95 } = opts;

  // 立即隐藏（避免 mount 后到 ScrollTrigger 触发前的"先看到再消失"闪现）
  gsap.set(el, { opacity: 0, y, force3D: true });

  ScrollTrigger.create({
    trigger: el,
    start: "top bottom-=100", // 元素顶部进入视口下方 100px 范围时触发
    once: true,
    onEnter: () => {
      gsap.to(el, {
        opacity: 1,
        y: 0,
        duration,
        delay,
        ease: "power3.out",
        force3D: true,
      });
    },
  });
}

/**
 * 跑马灯无限横向滚动 — 线性匀速，不要任何缓动
 * 适合 "GREEN THE PLANET ☀ ..." 这种重复带
 */
export function marqueeLoop(el: HTMLElement, durationSec: number = 30) {
  // 单组宽度的一半作为位移（前提：模板里把内容渲染了 2 份）
  const distance = el.scrollWidth / 2;
  return gsap.to(el, {
    x: -distance,
    duration: durationSec,
    ease: "none",
    repeat: -1,
  });
}

/**
 * 极轻微的悬浮呼吸 — Hero 装饰圆形图标用
 * 振幅 6px，慢节奏 3.5s，yoyo 来回
 */
export function gentleFloat(
  el: HTMLElement | HTMLElement[] | NodeListOf<Element>,
  amplitude: number = 6,
  delay: number = 0
) {
  gsap.to(el as gsap.TweenTarget, {
    y: -amplitude,
    duration: 4.5,
    ease: "sine.inOut",
    yoyo: true,
    repeat: -1,
    delay,
    force3D: true,
  });
}
