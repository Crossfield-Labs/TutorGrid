/**
 * 当前 Chat Session 状态
 *
 * 用途：
 *   - HyperdocPage 进入时把 tile.metadata.sessionId 写到这里
 *   - 顶层 Toolbox/ChatAssistant 通过这里拿到当前 session
 *   - BoardPage / 无文档场景使用 GLOBAL_SESSION_ID 兜底
 *
 * 注意：消息本身存在 messageStore，这里只存"现在在聊哪个 session"。
 */

import { defineStore } from "pinia";

export const GLOBAL_SESSION_ID = "session_global";

export const useChatSessionStore = defineStore("chatSession", {
  state: () => ({
    currentSessionId: GLOBAL_SESSION_ID as string,
    currentDocId: "" as string,
    courseId: "" as string,    // 进 RAG 时把这个传给后端
  }),

  actions: {
    setSession(sessionId: string, docId = "") {
      this.currentSessionId = sessionId || GLOBAL_SESSION_ID;
      this.currentDocId = docId;
    },
    resetToGlobal() {
      this.currentSessionId = GLOBAL_SESSION_ID;
      this.currentDocId = "";
    },
    setCourseId(courseId: string) {
      this.courseId = courseId;
    },
  },
});

/** 生成一个新 session id（uuid v4 兼容） */
export function makeSessionId(): string {
  // crypto.randomUUID 在 Electron / 现代浏览器都可用
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `sess_${crypto.randomUUID().replace(/-/g, "")}`;
  }
  return `sess_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}
