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
    async init() {
      if (this.loaded) return;
      const api = getApi();
      if (!api) {
        console.warn("[workspaceStore] not in Electron, using browser demo tiles");
        this.root = "演示工作区";
        this.tiles = [
          { id: "demo-note-1", column: "TODO", order: 0, title: "📝 开始你的第一个笔记", description: "双击磁贴编辑内容，单击右下角 Chat 使用 AI 对话。", kind: "note" as const, createdAt: Date.now(), updatedAt: Date.now() },
          { id: "demo-file-1", column: "TODO", order: 1, title: "📄 拖入课件文件", description: "在 Electron 中可导入 PDF/PPT/Word 并自动索引到知识库。", kind: "note" as const, createdAt: Date.now(), updatedAt: Date.now() },
          { id: "demo-hyper-1", column: "INPROGRESS", order: 0, title: "📖 新建 Hyper 文档示例", description: "在多人协作板中点击 + 按钮 → 开启「创建为 Hyper 文档」→ 新建。", kind: "note" as const, createdAt: Date.now(), updatedAt: Date.now() },
          { id: "demo-task-1", column: "INPROGRESS", order: 1, title: "🤖 AI 编排任务", description: "进入 Hyper 文档后输入 /task 命令即可触发编排任务。", kind: "note" as const, createdAt: Date.now(), updatedAt: Date.now() },
          { id: "demo-done-1", column: "DONE", order: 0, title: "✅ Chat SSE 端点已就绪", description: "POST /api/chat/stream 支持 RAG + Tavily 流式对话。", kind: "note" as const, createdAt: Date.now(), updatedAt: Date.now() },
          { id: "demo-done-2", column: "DONE", order: 1, title: "✅ 编排引擎 V5 已适配", description: "WebSocket /ws/orchestrator 支持 task.create/step/result 事件流。", kind: "note" as const, createdAt: Date.now(), updatedAt: Date.now() },
        ];
        this.columns = [...DEFAULT_COLUMNS];
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
