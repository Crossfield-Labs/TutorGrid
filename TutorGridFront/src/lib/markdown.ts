/**
 * Markdown 渲染（chat 气泡 + 文档 AI 气泡共用）
 *
 * 用 marked 解析 + DOMPurify 防 XSS
 * 流式场景反复调用安全：marked.parse 是纯函数，无内部状态
 */

import { marked } from "marked";
import DOMPurify from "dompurify";

marked.setOptions({
  gfm: true,
  breaks: true,   // 单换行也变 <br>，更适合 chat
});

export function renderMarkdown(text: string): string {
  if (!text) return "";
  const raw = marked.parse(text) as string;
  return DOMPurify.sanitize(raw, {
    USE_PROFILES: { html: true },
    ADD_ATTR: ["target", "rel"],
  });
}

/**
 * 给所有外链 a 标签加 target="_blank" + rel
 * Electron 里点链接会被 main.ts 的 setWindowOpenHandler 拦下来用系统浏览器打开
 */
export function postProcessLinks(html: string): string {
  return html.replace(
    /<a\s+([^>]*?)href="(https?:\/\/[^"]+)"([^>]*)>/gi,
    (_, pre, href, post) =>
      `<a ${pre}href="${href}"${post} target="_blank" rel="noopener noreferrer">`
  );
}
