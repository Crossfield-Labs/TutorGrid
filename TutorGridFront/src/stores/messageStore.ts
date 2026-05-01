/**
 * 统一消息 Store (F10)
 *
 * 文档区 AiBubbleNode 和右下角 ChatAssistant 浮窗共享同一份消息时间线。
 * 一个 Hyper 文档对应一个 sessionId（持久化在 tile.metadata 里）。
 *
 * 数据流：
 *   - DocumentEditor 触发 slash 命令 → addUserMessage + startAiMessage + 走 SSE → appendDelta
 *   - ChatAssistant 在浮窗里发消息 → 同上
 *   - 两边的视图都从 getSessionMessages(sessionId) 读取，实时同步
 */

import { defineStore } from "pinia";
import type { ChatCitation } from "@/lib/chat-sse";

export interface MessageMetadata {
  citations?: ChatCitation[];
  toolsUsed?: string[];
  searchResults?: Array<{
    title?: string;
    url?: string;
    content?: string;
    score?: number;
  }>;
  command?: string;          // 触发命令（explain-selection 等）
  origin?: "document" | "chat";  // 来源 UI
}

export interface UnifiedMessage {
  id: string;
  sessionId: string;
  role: "user" | "ai" | "system";
  content: string;
  metadata?: MessageMetadata;
  timestamp: number;
  streaming?: boolean;
  errored?: boolean;
}

interface MessageStoreState {
  // 按 sessionId 分组的消息列表
  messagesBySession: Record<string, UnifiedMessage[]>;
}

let _idCounter = 0;
const makeId = (prefix: string) =>
  `${prefix}_${Date.now().toString(36)}_${(_idCounter++).toString(36)}`;

export const useMessageStore = defineStore("messages", {
  state: (): MessageStoreState => ({
    messagesBySession: {},
  }),

  getters: {
    getSessionMessages: (state) => (sessionId: string) =>
      state.messagesBySession[sessionId] ?? [],

    findMessage: (state) => (sessionId: string, id: string) =>
      (state.messagesBySession[sessionId] ?? []).find((m) => m.id === id) ??
      null,

    lastMessage: (state) => (sessionId: string) => {
      const list = state.messagesBySession[sessionId] ?? [];
      return list[list.length - 1] ?? null;
    },
  },

  actions: {
    _ensureBucket(sessionId: string): UnifiedMessage[] {
      if (!this.messagesBySession[sessionId]) {
        this.messagesBySession[sessionId] = [];
      }
      return this.messagesBySession[sessionId];
    },

    /** 用户发送一条消息 */
    addUserMessage(
      sessionId: string,
      content: string,
      origin: "document" | "chat" = "chat",
      command?: string
    ): UnifiedMessage {
      const msg: UnifiedMessage = {
        id: makeId("u"),
        sessionId,
        role: "user",
        content,
        timestamp: Date.now(),
        metadata: { origin, command },
      };
      this._ensureBucket(sessionId).push(msg);
      return msg;
    },

    /** 起一条流式 AI 占位消息，返回的 id 用于后续 appendDelta */
    startAiMessage(
      sessionId: string,
      origin: "document" | "chat" = "chat",
      command?: string
    ): UnifiedMessage {
      const msg: UnifiedMessage = {
        id: makeId("a"),
        sessionId,
        role: "ai",
        content: "",
        streaming: true,
        timestamp: Date.now(),
        metadata: { origin, command, citations: [], toolsUsed: [] },
      };
      this._ensureBucket(sessionId).push(msg);
      return msg;
    },

    /** SSE delta 帧追加 */
    appendDelta(sessionId: string, messageId: string, delta: string) {
      const msg = (this.messagesBySession[sessionId] ?? []).find(
        (m) => m.id === messageId
      );
      if (!msg) return;
      msg.content += delta;
    },

    /** SSE 完成 */
    finishMessage(sessionId: string, messageId: string) {
      const msg = (this.messagesBySession[sessionId] ?? []).find(
        (m) => m.id === messageId
      );
      if (!msg) return;
      msg.streaming = false;
    },

    /** SSE 错误 */
    failMessage(sessionId: string, messageId: string, errorText: string) {
      const msg = (this.messagesBySession[sessionId] ?? []).find(
        (m) => m.id === messageId
      );
      if (!msg) return;
      msg.streaming = false;
      msg.errored = true;
      if (!msg.content) msg.content = `[出错] ${errorText}`;
    },

    addCitations(
      sessionId: string,
      messageId: string,
      citations: ChatCitation[]
    ) {
      const msg = (this.messagesBySession[sessionId] ?? []).find(
        (m) => m.id === messageId
      );
      if (!msg) return;
      if (!msg.metadata) msg.metadata = {};
      msg.metadata.citations = [
        ...(msg.metadata.citations ?? []),
        ...citations,
      ];
    },

    addSearchResults(
      sessionId: string,
      messageId: string,
      results: Array<{ title?: string; url?: string; content?: string; score?: number }>
    ) {
      const msg = (this.messagesBySession[sessionId] ?? []).find(
        (m) => m.id === messageId
      );
      if (!msg) return;
      if (!msg.metadata) msg.metadata = {};
      msg.metadata.searchResults = [
        ...(msg.metadata.searchResults ?? []),
        ...results,
      ];
    },

    addToolUsed(sessionId: string, messageId: string, tool: string) {
      const msg = (this.messagesBySession[sessionId] ?? []).find(
        (m) => m.id === messageId
      );
      if (!msg) return;
      if (!msg.metadata) msg.metadata = {};
      const used = msg.metadata.toolsUsed ?? [];
      if (!used.includes(tool)) used.push(tool);
      msg.metadata.toolsUsed = used;
    },

    clearSession(sessionId: string) {
      delete this.messagesBySession[sessionId];
    },
  },
});
