import { app, BrowserWindow, dialog, ipcMain, shell } from "electron";
import path from "node:path";
import fs from "node:fs";
import { randomUUID } from "node:crypto";

const devServerUrl = process.env.VITE_DEV_SERVER_URL;
const isDevelopment = Boolean(devServerUrl);

const DEFAULT_WORKSPACE_ROOT = "D:\\SoftInnovationCompetition\\TestFolder";
let workspaceRoot = DEFAULT_WORKSPACE_ROOT;

let mainWindow: BrowserWindow | null = null;

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 700,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow?.show();
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  if (isDevelopment && devServerUrl) {
    mainWindow.loadURL(new URL("index.html", devServerUrl).toString());
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

function workspacePaths() {
  return {
    root: workspaceRoot,
    hyperdocs: path.join(workspaceRoot, "hyperdocs"),
    tilesJson: path.join(workspaceRoot, "tiles.json"),
  };
}

async function ensureDirs() {
  const p = workspacePaths();
  await fs.promises.mkdir(p.root, { recursive: true });
  await fs.promises.mkdir(p.hyperdocs, { recursive: true });
}

function resolveSafe(relPath: string): string {
  const full = path.resolve(workspaceRoot, relPath);
  if (!full.startsWith(path.resolve(workspaceRoot))) {
    throw new Error("Path escapes workspace root");
  }
  return full;
}

function sanitizeName(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, "_").replace(/^\.+/, "") || "untitled";
}

async function uniqueRootName(originalName: string): Promise<string> {
  const safe = sanitizeName(originalName);
  const dot = safe.lastIndexOf(".");
  const stem = dot > 0 ? safe.slice(0, dot) : safe;
  const ext = dot > 0 ? safe.slice(dot) : "";
  let candidate = safe;
  let i = 1;
  while (true) {
    try {
      await fs.promises.access(path.join(workspaceRoot, candidate));
    } catch {
      return candidate;
    }
    candidate = `${stem} (${i})${ext}`;
    i++;
  }
}

const ROOT_RESERVED = new Set(["tiles.json"]);
const ROOT_RESERVED_DIRS = new Set(["hyperdocs"]);

function registerIpcHandlers() {
  ipcMain.handle("app:getInfo", () => ({
    name: app.getName(),
    version: app.getVersion(),
    userDataPath: app.getPath("userData"),
    isDevelopment,
  }));

  ipcMain.handle("workspace:pickFolder", async () => {
    const result = await dialog.showOpenDialog({
      title: "选择工作区文件夹",
      properties: ["openDirectory"],
    });
    if (result.canceled) return null;
    return result.filePaths[0];
  });

  ipcMain.handle("workspace:getRoot", async () => {
    await ensureDirs();
    return workspaceRoot;
  });

  ipcMain.handle("workspace:setRoot", async (_, newRoot: string) => {
    workspaceRoot = newRoot;
    await ensureDirs();
    return workspaceRoot;
  });

  ipcMain.handle("workspace:loadTiles", async () => {
    await ensureDirs();
    const p = workspacePaths();
    try {
      const text = await fs.promises.readFile(p.tilesJson, "utf-8");
      return JSON.parse(text);
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code === "ENOENT") return null;
      throw e;
    }
  });

  ipcMain.handle("workspace:saveTiles", async (_, data: unknown) => {
    await ensureDirs();
    const p = workspacePaths();
    await fs.promises.writeFile(
      p.tilesJson,
      JSON.stringify(data, null, 2),
      "utf-8"
    );
  });

  ipcMain.handle(
    "workspace:importFile",
    async (_, payload: { buffer: Uint8Array; originalName: string }) => {
      await ensureDirs();
      const filename = await uniqueRootName(payload.originalName);
      const fullPath = path.join(workspaceRoot, filename);
      await fs.promises.writeFile(fullPath, Buffer.from(payload.buffer));
      return { relPath: filename };
    }
  );

  ipcMain.handle("workspace:listRootFiles", async () => {
    await ensureDirs();
    const entries = await fs.promises.readdir(workspaceRoot, {
      withFileTypes: true,
    });
    const result: { name: string; size: number; mtime: number }[] = [];
    for (const entry of entries) {
      if (!entry.isFile()) continue;
      if (ROOT_RESERVED.has(entry.name)) continue;
      if (ROOT_RESERVED_DIRS.has(entry.name)) continue;
      const stat = await fs.promises.stat(
        path.join(workspaceRoot, entry.name)
      );
      result.push({
        name: entry.name,
        size: stat.size,
        mtime: stat.mtimeMs,
      });
    }
    return result;
  });

  ipcMain.handle("workspace:fileExists", async (_, relPath: string) => {
    try {
      const fullPath = resolveSafe(relPath);
      await fs.promises.access(fullPath);
      return true;
    } catch {
      return false;
    }
  });

  ipcMain.handle("workspace:readFileBuffer", async (_, relPath: string) => {
    const fullPath = resolveSafe(relPath);
    const data = await fs.promises.readFile(fullPath);
    return new Uint8Array(data);
  });

  ipcMain.handle("workspace:readText", async (_, relPath: string) => {
    const fullPath = resolveSafe(relPath);
    return fs.promises.readFile(fullPath, "utf-8");
  });

  ipcMain.handle(
    "workspace:writeText",
    async (_, payload: { relPath: string; content: string }) => {
      const fullPath = resolveSafe(payload.relPath);
      await fs.promises.mkdir(path.dirname(fullPath), { recursive: true });
      await fs.promises.writeFile(fullPath, payload.content, "utf-8");
    }
  );

  ipcMain.handle(
    "workspace:createHyperdoc",
    async (_, initialContent: string = "") => {
      await ensureDirs();
      const p = workspacePaths();
      const id = randomUUID();
      const filename = `${id}.md`;
      const fullPath = path.join(p.hyperdocs, filename);
      await fs.promises.writeFile(fullPath, initialContent, "utf-8");
      return { relPath: `hyperdocs/${filename}` };
    }
  );

  ipcMain.handle("workspace:deleteFile", async (_, relPath: string) => {
    const fullPath = resolveSafe(relPath);
    try {
      await fs.promises.unlink(fullPath);
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code !== "ENOENT") throw e;
    }
  });

  ipcMain.handle("workspace:openExternal", async (_, relPath: string) => {
    const fullPath = resolveSafe(relPath);
    await shell.openPath(fullPath);
  });
}

const gotLock = app.requestSingleInstanceLock();

if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (!mainWindow) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  });

  app.whenReady().then(() => {
    registerIpcHandlers();
    createMainWindow();

    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createMainWindow();
      }
    });
  });
}

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
