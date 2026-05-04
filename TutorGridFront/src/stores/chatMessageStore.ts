/**
 * ChatMessage Store（Step 2）
 *
 * 取代旧 messageStore 在 chat 区域的角色。
 * 数据从后端 SQLite 拉取（持久化），SSE 期间实时 append 到内存。
 *
 * 设计：
 *   - fetchBySession：从 GET /api/chats/{id}/messages 拉历史
 *   - SSE 期间：startAiPlaceholder + appendDelta + finishAiMessage
 *     （后端会自动写最终的完整 AI 消息到库；前端只用本地态实时展示流式效果）
 *   - 切换 session 时如果还没拉过就 fetch
 */

import { defineStore } from "pinia";
import type { ChatCitation } from "@/lib/chat-sse";
import { useSnackbarStore } from "@/stores/snackbarStore";

const API_BASE = "http://127.0.0.1:8000";

export interface ChatMessageMetadata {
  citations?: ChatCitation[];
  toolsUsed?: string[];
  searchResults?: Array<{
    title?: string;
    url?: string;
    content?: string;
    score?: number;
  }>;
  origin?: "chat" | "document";
  command?: string;
  sourceNodeId?: string; // 文档→Chat 引用消息时记的源节点 id
}

export interface ChatMessage {
  id: string;
  sessionId: string;
  role: "user" | "ai" | "system";
  content: string;
  metadata?: ChatMessageMetadata;
  timestamp: number;
  // 本地态（不写库，仅渲染用）
  streaming?: boolean;
  errored?: boolean;
}

interface State {
  messagesBySession: Record<string, ChatMessage[]>;
  loading: Record<string, boolean>;
  loadedOnce: Record<string, boolean>; // 记录该 session 是否已 fetch 过
}

let _idCounter = 0;
const localId = (prefix: string) =>
  `${prefix}_${Date.now().toString(36)}_${(_idCounter++).toString(36)}`;

export const useChatMessageStore = defineStore("chatMessage", {
  state: (): State => ({
    messagesBySession: {},
    loading: {},
    loadedOnce: {},
  }),

  getters: {
    messagesOf: (state) => (sessionId: string) =>
      state.messagesBySession[sessionId] ?? [],
    isLoading: (state) => (sessionId: string) => !!state.loading[sessionId],
  },

  actions: {
    _bucket(sessionId: string): ChatMessage[] {
      if (!this.messagesBySession[sessionId]) {
        this.messagesBySession[sessionId] = [];
      }
      return this.messagesBySession[sessionId];
    },

    async fetchBySession(
      sessionId: string,
      opts: { force?: boolean } = {}
    ): Promise<ChatMessage[]> {
      if (!sessionId) return [];
      if (!opts.force && this.loadedOnce[sessionId]) {
        return this.messagesBySession[sessionId] ?? [];
      }
      this.loading[sessionId] = true;
      try {
        const res = await fetch(
          `${API_BASE}/api/chats/${sessionId}/messages?limit=200`
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const list = (await res.json()) as ChatMessage[];
        this.messagesBySession[sessionId] = list;
        this.loadedOnce[sessionId] = true;
        return list;
      } catch (err) {
        useSnackbarStore().showErrorMessage(
          `加载消息失败: ${(err as Error).message}`
        );
        return [];
      } finally {
        this.loading[sessionId] = false;
      }
    },

    /**
     * 用户发出消息：本地立刻 push 一条用于即时显示
     * 后端 SSE 会自动写库，前端不重复写
     */
    pushUserMessage(sessionId: string, content: string): ChatMessage {
      const msg: ChatMessage = {
        id: localId("u"),
        sessionId,
        role: "user",
        content,
        timestamp: Date.now(),
        metadata: { origin: "chat" },
      };
      this._bucket(sessionId).push(msg);
      return msg;
    },

    /**
     * AI 占位消息：流式开始时调用，拿到 id 给 appendDelta 用
     */
    startAiPlaceholder(sessionId: string): ChatMessage {
      const msg: ChatMessage = {
        id: localId("a"),
        sessionId,
        role: "ai",
        content: "",
        streaming: true,
        timestamp: Date.now(),
        metadata: { origin: "chat", citations: [], toolsUsed: [] },
      };
      this._bucket(sessionId).push(msg);
      return msg;
    },

    appendDelta(sessionId: string, messageId: string, delta: string) {
      const msg = (this.messagesBySession[sessionId] ?? []).find(
        (m) => m.id === messageId
      );
      if (msg) msg.content += delta;
    },

    finishAi(sessionId: string, messageId: string) {
      const msg = (this.messagesBySession[sessionId] ?? []).find(
        (m) => m.id === messageId
      );
      if (msg) msg.streaming = false;
    },

    failAi(sessionId: string, messageId: string, errorText: string) {
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

    /**
     * 跨视图同步：从文档 AiBubbleNode 注入一条引用消息
     * 不走 SSE，仅本地显示 + 可选写库
     */
    pushQuoteFromDocument(
      sessionId: string,
      content: string,
      sourceNodeId: string
    ): ChatMessage {
      const msg: ChatMessage = {
        id: localId("q"),
        sessionId,
        role: "user",
        content,
        timestamp: Date.now(),
        metadata: { origin: "document", sourceNodeId },
      };
      this._bucket(sessionId).push(msg);
      // 不主动写库（用户后续问答会走 SSE 自动持久化），让首条引用消息也持久化的话需要额外 POST
      this._persistQuote(sessionId, msg);
      return msg;
    },

    async _persistQuote(sessionId: string, msg: ChatMessage) {
      try {
        await fetch(`${API_BASE}/api/chats/${sessionId}/messages`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            role: msg.role,
            content: msg.content,
            metadata: msg.metadata ?? {},
          }),
        });
      } catch (err) {
        console.warn("[chatMessageStore] persist quote failed", err);
      }
    },
  },
});
