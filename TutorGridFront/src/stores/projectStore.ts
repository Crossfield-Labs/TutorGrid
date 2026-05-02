/**
 * 工作区元数据 Store（产品级"工作区"概念）
 *
 * 用途：
 *   - 管理工作区列表（CRUD via REST /api/workspaces）
 *   - 持有当前选中的工作区（含背景图等视觉外观）
 *   - 切换工作区时联动现有 workspaceStore.setRoot 切换 Electron 文件根
 *
 * 与现有 workspaceStore 的关系：
 *   - workspaceStore  = Electron 当前文件系统根目录 + 磁贴管理（不动）
 *   - projectStore    = 产品级工作区元数据（本 store，新增）
 *   - 切换 project    → 调用 workspaceStore.setRoot(project.fsRoot)
 *
 * UI 上"工作区"指 Project；workspaceStore 是底层实现细节。
 */

import { defineStore } from "pinia";
import { useSnackbarStore } from "@/stores/snackbarStore";
import { useWorkspaceStore } from "@/stores/workspaceStore";

const API_BASE = "http://127.0.0.1:8000";

export interface ProjectAppearance {
  topBarBg: string;     // BoardPage 顶部 AppBar 背景图 URL（可空）
  pageBg: string;       // 整页背景图 URL（可空，对应 LandingLayout body 背景）
  sidebarColor: string; // Sidebar 折叠列表上的色块（可空）
}

export interface Project {
  id: string;
  name: string;
  fsRoot: string;
  appearance: ProjectAppearance;
  createdAt: number;
  updatedAt: number;
}

export interface HyperdocMeta {
  id: string;
  workspaceId: string;
  title: string;
  fileRelPath: string;
  createdAt: number;
  lastEditedAt: number;
}

interface ProjectStoreState {
  list: Project[];
  currentId: string;
  hyperdocsByProject: Record<string, HyperdocMeta[]>;
  loading: boolean;
  loadError: string;
}

const EMPTY_APPEARANCE: ProjectAppearance = {
  topBarBg: "",
  pageBg: "",
  sidebarColor: "",
};

export const useProjectStore = defineStore("project", {
  state: (): ProjectStoreState => ({
    list: [],
    currentId: "",
    hyperdocsByProject: {},
    loading: false,
    loadError: "",
  }),

  getters: {
    current(state): Project | null {
      return state.list.find((p) => p.id === state.currentId) ?? null;
    },
    currentAppearance(): ProjectAppearance {
      return this.current?.appearance ?? EMPTY_APPEARANCE;
    },
    hyperdocsOfCurrent(state): HyperdocMeta[] {
      return state.currentId ? state.hyperdocsByProject[state.currentId] ?? [] : [];
    },
  },

  actions: {
    async fetchList() {
      this.loading = true;
      this.loadError = "";
      try {
        const res = await fetch(`${API_BASE}/api/workspaces`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        this.list = (await res.json()) as Project[];
      } catch (err) {
        this.loadError = (err as Error).message;
        useSnackbarStore().showErrorMessage(`加载工作区失败: ${this.loadError}`);
      } finally {
        this.loading = false;
      }
    },

    async createProject(payload: {
      name: string;
      fsRoot: string;
      appearance?: Partial<ProjectAppearance>;
    }): Promise<Project | null> {
      try {
        const body = {
          name: payload.name,
          fsRoot: payload.fsRoot,
          appearance: { ...EMPTY_APPEARANCE, ...(payload.appearance ?? {}) },
        };
        const res = await fetch(`${API_BASE}/api/workspaces`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const detail = await res.text();
          throw new Error(detail || `HTTP ${res.status}`);
        }
        const created = (await res.json()) as Project;
        this.list.push(created);
        useSnackbarStore().showSuccessMessage(`已创建工作区「${created.name}」`);
        return created;
      } catch (err) {
        useSnackbarStore().showErrorMessage(`创建失败: ${(err as Error).message}`);
        return null;
      }
    },

    async updateProject(
      id: string,
      patch: Partial<Pick<Project, "name" | "fsRoot" | "appearance">>
    ): Promise<Project | null> {
      try {
        const res = await fetch(`${API_BASE}/api/workspaces/${id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const updated = (await res.json()) as Project;
        const idx = this.list.findIndex((p) => p.id === id);
        if (idx >= 0) this.list[idx] = updated;
        return updated;
      } catch (err) {
        useSnackbarStore().showErrorMessage(`更新失败: ${(err as Error).message}`);
        return null;
      }
    },

    async deleteProject(id: string): Promise<boolean> {
      try {
        const res = await fetch(`${API_BASE}/api/workspaces/${id}`, {
          method: "DELETE",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        this.list = this.list.filter((p) => p.id !== id);
        delete this.hyperdocsByProject[id];
        if (this.currentId === id) this.currentId = "";
        return true;
      } catch (err) {
        useSnackbarStore().showErrorMessage(`删除失败: ${(err as Error).message}`);
        return false;
      }
    },

    /**
     * 切换当前工作区 — 同步联动 Electron 的 workspaceStore.setRoot
     * 让现有磁贴/文件加载逻辑自动按新目录刷新
     */
    async setCurrent(id: string) {
      const target = this.list.find((p) => p.id === id);
      if (!target) return;
      this.currentId = id;
      // 同步底层 Electron 文件系统 root
      try {
        const ws = useWorkspaceStore();
        if (typeof (ws as any).setWorkspaceRoot === "function") {
          await (ws as any).setWorkspaceRoot(target.fsRoot);
        }
      } catch (err) {
        // workspaceStore 可能没暴露 setRoot，不致命
        console.warn("[projectStore] 联动 workspaceStore 失败", err);
      }
    },

    async fetchHyperdocs(projectId: string) {
      try {
        const res = await fetch(
          `${API_BASE}/api/workspaces/${projectId}/hyperdocs`
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        this.hyperdocsByProject[projectId] = (await res.json()) as HyperdocMeta[];
      } catch (err) {
        useSnackbarStore().showErrorMessage(
          `加载 Hyperdoc 列表失败: ${(err as Error).message}`
        );
      }
    },
  },
});
