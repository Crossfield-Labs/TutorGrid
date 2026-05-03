import { defineStore } from "pinia";
import { useSnackbarStore } from "@/stores/snackbarStore";

export type TileKind = "note" | "file" | "hyperdoc";

export type FileExt =
  | "pdf"
  | "pptx"
  | "ppt"
  | "docx"
  | "doc"
  | "xlsx"
  | "xls"
  | "md"
  | "txt"
  | "png"
  | "jpg"
  | "jpeg"
  | "gif"
  | "webp"
  | "bmp"
  | "svg"
  | "other";

export interface FileSource {
  kind: "file";
  relPath: string;
  mime: string;
  ext: FileExt;
  originalName: string;
  size: number;
}

export interface HyperdocSource {
  kind: "hyperdoc";
  relPath: string;
}

export type TileSource = FileSource | HyperdocSource;

export interface TileMetadata {
  sessionId?: string;
  courseId?: string;
  [key: string]: any;
}

export interface Tile {
  id: string;
  column: string;
  order: number;
  title: string;
  description?: string;
  kind: TileKind;
  source?: TileSource;
  pinned?: boolean;
  metadata?: TileMetadata;
  createdAt: number;
  updatedAt: number;
}

interface TilesFile {
  version: 1;
  columns: string[];
  tiles: Tile[];
}

const DEFAULT_COLUMNS = ["TODO", "INPROGRESS", "TESTING", "DONE"];

const IMAGE_EXTS = new Set<FileExt>([
  "png",
  "jpg",
  "jpeg",
  "gif",
  "webp",
  "bmp",
  "svg",
]);

const blobUrlCache = new Map<string, string>();

function genId(): string {
  return `tile_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function pickExt(filename: string): FileExt {
  const m = filename.toLowerCase().match(/\.([a-z0-9]+)$/);
  const ext = m?.[1] ?? "";
  const known: FileExt[] = [
    "pdf",
    "pptx",
    "ppt",
    "docx",
    "doc",
    "xlsx",
    "xls",
    "md",
    "txt",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "bmp",
    "svg",
  ];
  return (known.includes(ext as FileExt) ? ext : "other") as FileExt;
}

function getApi() {
  return window.metaAgent?.workspace;
}

export const useWorkspaceStore = defineStore("workspace", {
  state: () => ({
    root: "" as string,
    columns: [...DEFAULT_COLUMNS],
    tiles: [] as Tile[],
    missing: {} as Record<string, boolean>,
    loaded: false,
    saveTimer: null as ReturnType<typeof setTimeout> | null,
  }),

  getters: {
    isElectron: () => Boolean(window.metaAgent?.workspace),
    tilesByColumn(state) {
      const map: Record<string, Tile[]> = {};
      state.columns.forEach((c) => (map[c] = []));
      state.tiles.forEach((t) => {
        if (!map[t.column]) map[t.column] = [];
        map[t.column].push(t);
      });
      Object.values(map).forEach((arr) =>
        arr.sort((a, b) => a.order - b.order)
      );
      return map;
    },
    findTile(state) {
      return (id: string) => state.tiles.find((t) => t.id === id);
    },
  },

  actions: {
    /**
     * 切换工作区根目录（projectStore 调用，联动磁贴重新加载）
     * 仅在 Electron 环境下生效。
     */
    async setWorkspaceRoot(newRoot: string) {
      const api = getApi();
      if (!api || !newRoot) return;
      try {
        await api.setRoot(newRoot);
        this.root = newRoot;
        this.loaded = false;
        this.tiles = [];
        this.missing = {};
        await this.init();
      } catch (e) {
        console.error("[workspaceStore] setWorkspaceRoot failed", e);
        useSnackbarStore().showErrorMessage(`切换工作区失败: ${String(e)}`);
      }
    },

    async init() {
      if (this.loaded) return;
      const api = getApi();
      if (!api) {
        console.warn("[workspaceStore] not in Electron, skipping init");
        this.loaded = true;
        return;
      }
      try {
        this.root = await api.getRoot();
        const data = (await api.loadTiles()) as TilesFile | null;
        if (data?.tiles) {
          this.tiles = data.tiles;
          this.columns = data.columns?.length ? data.columns : DEFAULT_COLUMNS;
        }
        await this.reconcile();
        this.loaded = true;
      } catch (e) {
        console.error("[workspaceStore] init failed", e);
        useSnackbarStore().showErrorMessage(`工作区初始化失败: ${String(e)}`);
        this.loaded = true;
      }
    },

    async reconcile() {
      const api = getApi();
      if (!api) return;

      // 1. 列出工作区根目录文件
      const rootFiles = await api.listRootFiles();

      // 2. 标记 tiles.json 中文件已不存在的磁贴
      const missing: Record<string, boolean> = {};
      for (const tile of this.tiles) {
        if (!tile.source) continue;
        const exists = await api.fileExists(tile.source.relPath);
        if (!exists) missing[tile.id] = true;
      }
      this.missing = missing;

      // 3. 工作区根目录里的文件，若未对应任何磁贴 → 自动建磁贴
      const tiledRootNames = new Set(
        this.tiles
          .filter(
            (t) =>
              t.source?.kind === "file" &&
              !t.source.relPath.includes("/") &&
              !t.source.relPath.includes("\\")
          )
          .map((t) => t.source!.relPath)
      );
      const defaultColumn = this.columns[0] || "TODO";
      let added = false;
      for (const f of rootFiles) {
        if (tiledRootNames.has(f.name)) continue;
        const ext = pickExt(f.name);
        const stem = f.name.replace(/\.[^.]+$/, "");
        const now = Date.now();
        this.tiles.push({
          id: genId(),
          column: defaultColumn,
          order: this.nextOrder(defaultColumn),
          title: stem,
          kind: "file",
          source: {
            kind: "file",
            relPath: f.name,
            mime: "",
            ext,
            originalName: f.name,
            size: f.size,
          },
          createdAt: now,
          updatedAt: now,
        });
        added = true;
      }
      if (added) this.scheduleSave();
    },

    scheduleSave() {
      if (this.saveTimer) clearTimeout(this.saveTimer);
      this.saveTimer = setTimeout(() => {
        this.saveNow();
      }, 300);
    },

    async saveNow() {
      const api = getApi();
      if (!api) return;
      // 显式构造纯对象，避免 Pinia/Vue reactive proxy 走 IPC structuredClone 失败
      const plainTiles = this.tiles.map((t) => ({
        id: t.id,
        column: t.column,
        order: t.order,
        title: t.title,
        description: t.description ?? "",
        kind: t.kind,
        source: !t.source
          ? undefined
          : t.source.kind === "file"
          ? {
              kind: "file" as const,
              relPath: t.source.relPath,
              mime: t.source.mime,
              ext: t.source.ext,
              originalName: t.source.originalName,
              size: t.source.size,
            }
          : { kind: "hyperdoc" as const, relPath: t.source.relPath },
        pinned: t.pinned ?? false,
        metadata: t.metadata ? { ...t.metadata } : undefined,
        createdAt: t.createdAt,
        updatedAt: t.updatedAt,
      }));
      const data = {
        version: 1 as const,
        columns: [...this.columns],
        tiles: plainTiles,
      };
      try {
        await api.saveTiles(data);
      } catch (e) {
        console.error("[workspaceStore] save failed", e);
        useSnackbarStore().showErrorMessage(`保存失败: ${String(e)}`);
      }
    },

    nextOrder(column: string): number {
      const inCol = this.tiles.filter((t) => t.column === column);
      return inCol.length > 0
        ? Math.max(...inCol.map((t) => t.order)) + 1
        : 0;
    },

    async addNote(column: string, title: string, description = "") {
      const now = Date.now();
      const tile: Tile = {
        id: genId(),
        column,
        order: this.nextOrder(column),
        title,
        description,
        kind: "note",
        createdAt: now,
        updatedAt: now,
      };
      this.tiles.unshift(tile);
      this.reorderColumn(column);
      this.scheduleSave();
      return tile;
    },

    async addFile(
      column: string,
      file: File,
      title?: string,
      description = ""
    ) {
      const api = getApi();
      if (!api) {
        useSnackbarStore().showErrorMessage("非桌面环境，无法导入文件");
        return null;
      }
      const ext = pickExt(file.name);
      const buffer = new Uint8Array(await file.arrayBuffer());
      const { relPath } = await api.importFile({
        buffer,
        originalName: file.name,
      });
      const now = Date.now();
      const stem = file.name.replace(/\.[^.]+$/, "");
      const tile: Tile = {
        id: genId(),
        column,
        order: this.nextOrder(column),
        title: title?.trim() || stem,
        description,
        kind: "file",
        source: {
          kind: "file",
          relPath,
          mime: file.type || "",
          ext,
          originalName: relPath,
          size: file.size,
        },
        createdAt: now,
        updatedAt: now,
      };
      this.tiles.unshift(tile);
      this.reorderColumn(column);
      this.scheduleSave();
      return tile;
    },

    async addHyperdoc(column: string, title: string, description = "") {
      const api = getApi();
      if (!api) {
        useSnackbarStore().showErrorMessage("非桌面环境，无法创建 Hyper 文档");
        return null;
      }
      const seed = `# ${title}\n\n`;
      const { relPath } = await api.createHyperdoc(seed);
      const now = Date.now();
      const tile: Tile = {
        id: genId(),
        column,
        order: this.nextOrder(column),
        title,
        description,
        kind: "hyperdoc",
        source: { kind: "hyperdoc", relPath },
        createdAt: now,
        updatedAt: now,
      };
      this.tiles.unshift(tile);
      this.reorderColumn(column);
      this.scheduleSave();

      // Step 2 #10：同步注册到 hyperdocs_meta 表，让 sidebar 能看到
      try {
        const { useProjectStore } = await import("@/stores/projectStore");
        const projectStore = useProjectStore();
        const projectId = projectStore.currentId;
        if (projectId) {
          const res = await fetch(
            `http://127.0.0.1:8000/api/workspaces/${projectId}/hyperdocs`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ title, fileRelPath: relPath }),
            }
          );
          if (res.ok) {
            // 刷新 sidebar 折叠列表
            await projectStore.fetchHyperdocs(projectId);
          }
        }
      } catch (e) {
        console.warn("[workspaceStore] hyperdoc meta 注册失败（非致命）", e);
      }

      return tile;
    },

    async updateTile(id: string, patch: Partial<Tile>) {
      const tile = this.findTile(id);
      if (!tile) return;
      Object.assign(tile, patch, { updatedAt: Date.now() });
      this.scheduleSave();
    },

    async setTileMetadata(id: string, patch: Partial<TileMetadata>) {
      const tile = this.findTile(id);
      if (!tile) return;
      tile.metadata = { ...(tile.metadata || {}), ...patch };
      tile.updatedAt = Date.now();
      this.scheduleSave();
    },

    async removeTile(id: string) {
      const idx = this.tiles.findIndex((t) => t.id === id);
      if (idx < 0) return;
      const tile = this.tiles[idx];
      const api = getApi();
      if (api && tile.source && !this.missing[id]) {
        try {
          await api.deleteFile(tile.source.relPath);
        } catch (e) {
          console.warn("[workspaceStore] file delete failed", e);
        }
        const cached = blobUrlCache.get(tile.source.relPath);
        if (cached) {
          URL.revokeObjectURL(cached);
          blobUrlCache.delete(tile.source.relPath);
        }
      }
      this.tiles.splice(idx, 1);
      delete this.missing[id];
      this.reorderColumn(tile.column);
      this.scheduleSave();
    },

    moveTile(id: string, toColumn: string, toIndex: number) {
      const tile = this.findTile(id);
      if (!tile) return;
      const fromColumn = tile.column;
      tile.column = toColumn;
      this.reorderColumn(fromColumn);
      const colTiles = this.tiles
        .filter((t) => t.column === toColumn && t.id !== id)
        .sort((a, b) => a.order - b.order);
      colTiles.splice(toIndex, 0, tile);
      colTiles.forEach((t, i) => (t.order = i));
      this.scheduleSave();
    },

    reorderColumn(column: string) {
      this.tiles
        .filter((t) => t.column === column)
        .sort((a, b) => a.order - b.order)
        .forEach((t, i) => (t.order = i));
    },

    async getBlobURL(relPath: string, mime: string): Promise<string | null> {
      const api = getApi();
      if (!api) return null;
      const cached = blobUrlCache.get(relPath);
      if (cached) return cached;
      try {
        const buffer = await api.readFileBuffer(relPath);
        const blob = new Blob([buffer], { type: mime || "application/octet-stream" });
        const url = URL.createObjectURL(blob);
        blobUrlCache.set(relPath, url);
        return url;
      } catch (e) {
        console.error("[workspaceStore] readFileBuffer failed", e);
        return null;
      }
    },

    async readText(relPath: string): Promise<string> {
      const api = getApi();
      if (!api) return "";
      return api.readText(relPath);
    },

    async writeText(relPath: string, content: string) {
      const api = getApi();
      if (!api) return;
      return api.writeText({ relPath, content });
    },

    async openExternal(relPath: string) {
      const api = getApi();
      if (!api) return;
      return api.openExternal(relPath);
    },

    isImage(ext: FileExt): boolean {
      return IMAGE_EXTS.has(ext);
    },
  },
});
