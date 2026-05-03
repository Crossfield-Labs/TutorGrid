/**
 * ChatSessionList Store（Step 2）
 *
 * 用途：管理"某个 hyperdoc 下所有 chat sessions"的列表 + CRUD
 *
 * 与现有 chatSessionStore 的区别：
 *   - chatSessionStore     = 当前活跃 session 状态（currentSessionId / currentDocId）
 *   - chatSessionListStore = sessions 列表数据（按 hyperdoc 分组），本 store
 */

import { defineStore } from "pinia";
import { useSnackbarStore } from "@/stores/snackbarStore";

const API_BASE = "http://127.0.0.1:8000";

export interface ChatSessionItem {
  id: string;
  hyperdocId: string;
  title: string;
  createdAt: number;
  lastActiveAt: number;
}

interface State {
  byHyperdoc: Record<string, ChatSessionItem[]>;
  loading: boolean;
}

export const useChatSessionListStore = defineStore("chatSessionList", {
  state: (): State => ({
    byHyperdoc: {},
    loading: false,
  }),

  getters: {
    sessionsOf: (state) => (hyperdocId: string) =>
      state.byHyperdoc[hyperdocId] ?? [],
  },

  actions: {
    async fetchByHyperdoc(hyperdocId: string): Promise<ChatSessionItem[]> {
      if (!hyperdocId) return [];
      this.loading = true;
      try {
        const res = await fetch(
          `${API_BASE}/api/hyperdocs/${hyperdocId}/chats`
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const list = (await res.json()) as ChatSessionItem[];
        this.byHyperdoc[hyperdocId] = list;
        return list;
      } catch (err) {
        useSnackbarStore().showErrorMessage(
          `加载会话列表失败: ${(err as Error).message}`
        );
        return [];
      } finally {
        this.loading = false;
      }
    },

    /**
     * 在指定 hyperdoc 下新建会话
     * 自动加入 byHyperdoc 列表
     */
    async create(
      hyperdocId: string,
      title = ""
    ): Promise<ChatSessionItem | null> {
      try {
        const res = await fetch(
          `${API_BASE}/api/hyperdocs/${hyperdocId}/chats`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title }),
          }
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const created = (await res.json()) as ChatSessionItem;
        if (!this.byHyperdoc[hyperdocId]) this.byHyperdoc[hyperdocId] = [];
        this.byHyperdoc[hyperdocId].unshift(created);
        return created;
      } catch (err) {
        useSnackbarStore().showErrorMessage(
          `新建会话失败: ${(err as Error).message}`
        );
        return null;
      }
    },

    /**
     * 确保至少有一个会话；没有则创建一个默认会话并返回
     */
    async ensureDefault(hyperdocId: string): Promise<ChatSessionItem | null> {
      const list = await this.fetchByHyperdoc(hyperdocId);
      if (list.length > 0) return list[0];
      return await this.create(hyperdocId, "默认会话");
    },

    async rename(
      sessionId: string,
      title: string
    ): Promise<ChatSessionItem | null> {
      try {
        const res = await fetch(`${API_BASE}/api/chats/${sessionId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const updated = (await res.json()) as ChatSessionItem;
        // 替换本地缓存
        const docList = this.byHyperdoc[updated.hyperdocId];
        if (docList) {
          const i = docList.findIndex((s) => s.id === sessionId);
          if (i >= 0) docList[i] = updated;
        }
        return updated;
      } catch (err) {
        useSnackbarStore().showErrorMessage(
          `改名失败: ${(err as Error).message}`
        );
        return null;
      }
    },

    async remove(sessionId: string): Promise<boolean> {
      try {
        const res = await fetch(`${API_BASE}/api/chats/${sessionId}`, {
          method: "DELETE",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        // 从所有 hyperdoc 缓存中清掉
        for (const docId of Object.keys(this.byHyperdoc)) {
          this.byHyperdoc[docId] = this.byHyperdoc[docId].filter(
            (s) => s.id !== sessionId
          );
        }
        return true;
      } catch (err) {
        useSnackbarStore().showErrorMessage(
          `删除会话失败: ${(err as Error).message}`
        );
        return false;
      }
    },
  },
});
