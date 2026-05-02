import { app, BrowserWindow, dialog, ipcMain, Menu, shell } from "electron";
import { spawn, type ChildProcess } from "node:child_process";
import http from "node:http";
import net from "node:net";
import path from "node:path";
import fs from "node:fs";
import { randomUUID } from "node:crypto";

const devServerUrl = process.env.VITE_DEV_SERVER_URL;
const isDevelopment = Boolean(devServerUrl);
const BACKEND_PORT = 8000;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;
const ORCHESTRATOR_PORT = 3210;
const REPO_ROOT = path.resolve(__dirname, "../..");
const APP_ICON_PNG = path.join(REPO_ROOT, "TutorGridFront", "build", "icons", "app-icon.png");
const APP_ICON_FALLBACK = path.join(REPO_ROOT, "TutorGridFront", "public", "favicon.png");

function buildPythonCandidates(): Array<{ command: string; args: string[] }> {
  const candidates: Array<{ command: string; args: string[] }> = [];
  const seen = new Set<string>();

  const pushCandidate = (command: string, args: string[] = []) => {
    const key = `${command}::${args.join(" ")}`;
    if (!command || seen.has(key)) return;
    seen.add(key);
    candidates.push({ command, args });
  };

  const envPython = process.env.PYTHON_EXECUTABLE?.trim();
  if (envPython) {
    pushCandidate(envPython);
  }

  const virtualEnv = process.env.VIRTUAL_ENV?.trim();
  if (virtualEnv) {
    pushCandidate(
      process.platform === "win32"
        ? path.join(virtualEnv, "Scripts", "python.exe")
        : path.join(virtualEnv, "bin", "python")
    );
  }

  const condaPrefix = process.env.CONDA_PREFIX?.trim();
  if (condaPrefix) {
    pushCandidate(
      process.platform === "win32"
        ? path.join(condaPrefix, "python.exe")
        : path.join(condaPrefix, "bin", "python")
    );
  }

  const repoVirtualEnvNames = [".venv", "venv", "env"];
  for (const name of repoVirtualEnvNames) {
    pushCandidate(
      process.platform === "win32"
        ? path.join(REPO_ROOT, name, "Scripts", "python.exe")
        : path.join(REPO_ROOT, name, "bin", "python")
    );
  }

  if (process.platform === "win32") {
    pushCandidate("python");
    pushCandidate("py", ["-3"]);
  } else {
    pushCandidate("python3");
    pushCandidate("python");
  }

  return candidates;
}

const PYTHON_CANDIDATES = buildPythonCandidates();

const DEFAULT_WORKSPACE_ROOT = "D:\\SoftInnovationCompetition\\TestFolder";
let workspaceRoot = DEFAULT_WORKSPACE_ROOT;

let mainWindow: BrowserWindow | null = null;
let httpBackendProcess: ChildProcess | null = null;
let orchestratorProcess: ChildProcess | null = null;

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function isBackendHealthy(): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(`${BACKEND_URL}/api/health`, (res) => {
      resolve((res.statusCode ?? 500) >= 200 && (res.statusCode ?? 500) < 300);
      res.resume();
    });
    req.on("error", () => resolve(false));
    req.setTimeout(1500, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForBackendReady(timeoutMs = 20000): Promise<boolean> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (await isBackendHealthy()) return true;
    await wait(500);
  }
  return false;
}

async function isOrchestratorHealthy(): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = net.createConnection(
      { host: "127.0.0.1", port: ORCHESTRATOR_PORT },
      () => {
        socket.end();
        resolve(true);
      }
    );
    socket.on("error", () => resolve(false));
    socket.setTimeout(1500, () => {
      socket.destroy();
      resolve(false);
    });
  });
}

async function waitForOrchestratorReady(timeoutMs = 20000): Promise<boolean> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (await isOrchestratorHealthy()) return true;
    await wait(500);
  }
  return false;
}

async function ensureHttpBackendStarted(): Promise<void> {
  if (await isBackendHealthy()) return;
  if (httpBackendProcess) {
    const ready = await waitForBackendReady();
    if (ready) return;
    throw new Error("本地 HTTP 后端进程存在，但健康检查未通过。");
  }

  const startupErrors: string[] = [];
  for (const candidate of PYTHON_CANDIDATES) {
    if (path.isAbsolute(candidate.command) && !fs.existsSync(candidate.command)) {
      startupErrors.push(`${candidate.command} 不存在`);
      continue;
    }
    const child = spawn(
      candidate.command,
      [
        ...candidate.args,
        "-m",
        "uvicorn",
        "backend.http_main:app",
        "--host",
        "127.0.0.1",
        "--port",
        String(BACKEND_PORT),
      ],
      {
        cwd: REPO_ROOT,
        windowsHide: true,
        stdio: ["ignore", "pipe", "pipe"],
      }
    );

    let spawnFailed = false;
    let exitedEarly = false;
    let spawnErrorMessage = "";
    child.once("error", (error) => {
      spawnFailed = true;
      spawnErrorMessage = error instanceof Error ? error.message : String(error);
    });
    child.once("exit", (code, signal) => {
      exitedEarly = true;
      if (!spawnErrorMessage) {
        spawnErrorMessage = `exit code=${code ?? "null"} signal=${signal ?? "null"}`;
      }
    });
    child.stdout?.on("data", (chunk) => {
      process.stdout.write(`[backend] ${chunk}`);
    });
    child.stderr?.on("data", (chunk) => {
      process.stderr.write(`[backend] ${chunk}`);
    });

    await wait(1200);
    if (spawnFailed) {
      child.removeAllListeners();
      startupErrors.push(`${candidate.command} ${candidate.args.join(" ")} 启动失败: ${spawnErrorMessage || "unknown error"}`);
      continue;
    }
    if (exitedEarly) {
      child.removeAllListeners();
      startupErrors.push(`${candidate.command} ${candidate.args.join(" ")} 启动后立即退出: ${spawnErrorMessage || "unknown error"}`);
      continue;
    }

    httpBackendProcess = child;
    const ready = await waitForBackendReady();
    if (ready) return;
    startupErrors.push(`${candidate.command} ${candidate.args.join(" ")} 已启动，但 ${BACKEND_URL}/api/health 未在超时时间内就绪`);
    try {
      child.kill();
    } catch {
      /* noop */
    }
    httpBackendProcess = null;
  }

  throw new Error(
    "无法自动拉起本地 HTTP 后端，请确认已安装 Python 及 requirements.txt 依赖。\n" +
      startupErrors.join("\n")
  );
}

async function ensureOrchestratorStarted(): Promise<void> {
  if (await isOrchestratorHealthy()) return;
  if (orchestratorProcess) {
    const ready = await waitForOrchestratorReady();
    if (ready) return;
    throw new Error("本地编排后端进程存在，但健康检查未通过。");
  }

  const startupErrors: string[] = [];
  for (const candidate of PYTHON_CANDIDATES) {
    if (path.isAbsolute(candidate.command) && !fs.existsSync(candidate.command)) {
      startupErrors.push(`${candidate.command} 不存在`);
      continue;
    }
    const child = spawn(
      candidate.command,
      [
        ...candidate.args,
        "-m",
        "backend.main",
        "--host",
        "127.0.0.1",
        "--port",
        String(ORCHESTRATOR_PORT),
      ],
      {
        cwd: REPO_ROOT,
        windowsHide: true,
        stdio: ["ignore", "pipe", "pipe"],
      }
    );

    let spawnFailed = false;
    let exitedEarly = false;
    let spawnErrorMessage = "";
    child.once("error", (error) => {
      spawnFailed = true;
      spawnErrorMessage = error instanceof Error ? error.message : String(error);
    });
    child.once("exit", (code, signal) => {
      exitedEarly = true;
      if (!spawnErrorMessage) {
        spawnErrorMessage = `exit code=${code ?? "null"} signal=${signal ?? "null"}`;
      }
    });
    child.stdout?.on("data", (chunk) => {
      process.stdout.write(`[orchestrator] ${chunk}`);
    });
    child.stderr?.on("data", (chunk) => {
      process.stderr.write(`[orchestrator] ${chunk}`);
    });

    await wait(1200);
    if (spawnFailed) {
      child.removeAllListeners();
      startupErrors.push(`${candidate.command} ${candidate.args.join(" ")} 启动失败: ${spawnErrorMessage || "unknown error"}`);
      continue;
    }
    if (exitedEarly) {
      child.removeAllListeners();
      startupErrors.push(`${candidate.command} ${candidate.args.join(" ")} 启动后立即退出: ${spawnErrorMessage || "unknown error"}`);
      continue;
    }

    orchestratorProcess = child;
    const ready = await waitForOrchestratorReady();
    if (ready) return;
    startupErrors.push(`${candidate.command} ${candidate.args.join(" ")} 已启动，但 ws://127.0.0.1:${ORCHESTRATOR_PORT}/ws/orchestrator 未在超时时间内就绪`);
    try {
      child.kill();
    } catch {
      /* noop */
    }
    orchestratorProcess = null;
  }

  throw new Error(
    "无法自动拉起本地编排后端，请确认已安装 Python 及 requirements.txt 依赖。\n" +
      startupErrors.join("\n")
  );
}

async function ensureBackendStarted(): Promise<void> {
  await ensureHttpBackendStarted();
  await ensureOrchestratorStarted();
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 700,
    show: false,
    title: "TutorGrid",
    icon: fs.existsSync(APP_ICON_PNG) ? APP_ICON_PNG : APP_ICON_FALLBACK,
    frame: false,             // 去掉 Windows 系统级 1-2px 客户区边框（拖拽 region 在 MainAppbar.vue 里已实现）
    titleBarStyle: "hidden",  // 保留：让 macOS 有交通灯按钮
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

  mainWindow.on("maximize", () => {
    mainWindow?.webContents.send("window:maximizedChanged", true);
  });
  mainWindow.on("unmaximize", () => {
    mainWindow?.webContents.send("window:maximizedChanged", false);
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  if (isDevelopment) {
    mainWindow.webContents.on("before-input-event", (event, input) => {
      const key = input.key.toLowerCase();
      const toggleDevTools =
        input.key === "F12" || (input.control && input.shift && key === "i");
      if (!toggleDevTools) return;
      event.preventDefault();
      mainWindow?.webContents.toggleDevTools();
    });
  }

  if (isDevelopment && devServerUrl) {
    mainWindow.loadURL(devServerUrl);
    mainWindow.webContents.once("did-finish-load", () => {
      mainWindow?.webContents.openDevTools({ mode: "detach" });
    });
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }

  mainWindow.webContents.on("before-input-event", (_event, input) => {
    if ((input.control || input.meta) && input.shift && input.key.toLowerCase() === "i") {
      mainWindow?.webContents.toggleDevTools();
    }
    if (input.key === "F12") {
      mainWindow?.webContents.toggleDevTools();
    }
  });
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
      await fs.promises.writeFile(fullPath, new Uint8Array(payload.buffer));
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

  // -------- 工作区资源（背景图等）：保存到 <targetRoot>/.assets/ ----------
  // 不依赖当前 workspaceRoot，因为创建工作区时新 root 还没切过来
  ipcMain.handle(
    "workspace:saveAssetTo",
    async (
      _,
      payload: { targetRoot: string; buffer: Uint8Array; originalName: string }
    ): Promise<{ relPath: string }> => {
      const { targetRoot, buffer, originalName } = payload;
      if (!targetRoot || !fs.existsSync(targetRoot)) {
        throw new Error(`目标目录不存在: ${targetRoot}`);
      }
      const assetsDir = path.join(targetRoot, ".assets");
      if (!fs.existsSync(assetsDir)) {
        fs.mkdirSync(assetsDir, { recursive: true });
      }
      const ext = (path.extname(originalName) || ".jpg").toLowerCase();
      const newName = `${randomUUID()}${ext}`;
      const fullPath = path.join(assetsDir, newName);
      // 直接传 Uint8Array（fs.writeFile 接受 ArrayBufferView）
      await fs.promises.writeFile(fullPath, buffer);
      // 返回相对 targetRoot 的路径，统一用 POSIX 斜杠
      return { relPath: `.assets/${newName}` };
    }
  );

  ipcMain.handle(
    "workspace:readAssetFrom",
    async (
      _,
      payload: { targetRoot: string; relPath: string }
    ): Promise<Uint8Array | null> => {
      const { targetRoot, relPath } = payload;
      if (!targetRoot || !relPath) return null;
      // 安全：禁止 .. 跳出 targetRoot
      const fullPath = path.resolve(targetRoot, relPath);
      const normRoot = path.resolve(targetRoot);
      if (!fullPath.startsWith(normRoot)) {
        throw new Error(`非法路径: ${relPath}`);
      }
      try {
        const buf = await fs.promises.readFile(fullPath);
        // 返回 Uint8Array（IPC 可序列化），renderer 用 new Blob([uint8]) 转 blob URL
        return new Uint8Array(buf);
      } catch (e) {
        if ((e as NodeJS.ErrnoException).code === "ENOENT") return null;
        throw e;
      }
    }
  );

  ipcMain.handle("window:minimize", () => {
    mainWindow?.minimize();
  });

  ipcMain.handle("window:toggleMaximize", () => {
    if (!mainWindow) return false;
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
      return false;
    }
    mainWindow.maximize();
    return true;
  });

  ipcMain.handle("window:close", () => {
    mainWindow?.close();
  });

  ipcMain.handle("window:isMaximized", () => {
    return mainWindow?.isMaximized() ?? false;
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

  app.whenReady().then(async () => {
    Menu.setApplicationMenu(null);
    registerIpcHandlers();
    try {
      await ensureBackendStarted();
    } catch (error) {
      console.error("[electron] backend startup failed", error);
      dialog.showErrorBox(
        "后端启动失败",
        error instanceof Error ? error.message : String(error)
      );
      app.quit();
      return;
    }
    createMainWindow();

    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createMainWindow();
      }
    });
  });
}

app.on("window-all-closed", () => {
  if (httpBackendProcess) {
    try {
      httpBackendProcess.kill();
    } catch {
      /* noop */
    }
    httpBackendProcess = null;
  }
  if (orchestratorProcess) {
    try {
      orchestratorProcess.kill();
    } catch {
      /* noop */
    }
    orchestratorProcess = null;
  }
  if (process.platform !== "darwin") {
    app.quit();
  }
});
