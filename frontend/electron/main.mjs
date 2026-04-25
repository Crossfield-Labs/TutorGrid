import { app, BrowserWindow, dialog, ipcMain } from "electron";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

let backendProcess = null;
let backendLogStream = null;

ipcMain.handle("desktop:pick-files", async (_event, payload) => {
  const rawOptions = payload && typeof payload === "object" ? payload : {};
  const multiple = Boolean(rawOptions.multiple);
  const title = typeof rawOptions.title === "string" && rawOptions.title.trim() ? rawOptions.title.trim() : "选择文件";
  const result = await dialog.showOpenDialog({
    title,
    properties: multiple ? ["openFile", "multiSelections"] : ["openFile"],
  });
  if (result.canceled) {
    return [];
  }
  return result.filePaths;
});

function resolveBackendBinaryPath() {
  const binaryName = process.platform === "win32" ? "pc-orchestrator-backend.exe" : "pc-orchestrator-backend";
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "backend-bin", binaryName);
  }
  return path.join(__dirname, "..", "..", "dist", binaryName);
}

function resolveBackendLogPath() {
  const customPath = process.env.ORCHESTRATOR_BACKEND_LOG;
  if (customPath && customPath.trim()) {
    return customPath.trim();
  }
  if (app.isPackaged) {
    return path.join(app.getPath("logs"), "pc-orchestrator-backend.log");
  }
  return path.join(__dirname, "..", "..", "scratch", "logs", "backend-dev.log");
}

function ensureLogStream() {
  if (backendLogStream) {
    return backendLogStream;
  }
  const logPath = resolveBackendLogPath();
  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  backendLogStream = fs.createWriteStream(logPath, { flags: "a" });
  return backendLogStream;
}

function writeBackendLog(line) {
  const stream = ensureLogStream();
  stream.write(`${new Date().toISOString()} ${line}\n`);
}

function bindBackendLogs(processHandle) {
  if (!processHandle) {
    return;
  }
  processHandle.stdout?.on("data", (chunk) => {
    const text = String(chunk).trimEnd();
    if (!text) {
      return;
    }
    writeBackendLog(`[stdout] ${text}`);
    if (!app.isPackaged) {
      // eslint-disable-next-line no-console
      console.log(`[backend] ${text}`);
    }
  });
  processHandle.stderr?.on("data", (chunk) => {
    const text = String(chunk).trimEnd();
    if (!text) {
      return;
    }
    writeBackendLog(`[stderr] ${text}`);
    // eslint-disable-next-line no-console
    console.error(`[backend] ${text}`);
  });
  processHandle.on("exit", (code, signal) => {
    writeBackendLog(`[exit] code=${String(code)} signal=${String(signal)}`);
    if (!app.isPackaged) {
      // eslint-disable-next-line no-console
      console.log(`[backend] exited code=${String(code)} signal=${String(signal)}`);
    }
  });
}

function spawnBackend(command, args, cwd) {
  backendProcess = spawn(command, args, {
    cwd,
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  bindBackendLogs(backendProcess);
}

function startBackend() {
  const args = ["--host", "127.0.0.1", "--port", "3210"];
  const backendPath = resolveBackendBinaryPath();
  if (fs.existsSync(backendPath)) {
    spawnBackend(backendPath, args, app.isPackaged ? process.resourcesPath : path.join(__dirname, "..", ".."));
    return;
  }
  if (!app.isPackaged) {
    const repoRoot = path.join(__dirname, "..", "..");
    const pythonCommand = process.env.ORCHESTRATOR_PYTHON || "python";
    spawnBackend(pythonCommand, ["-m", "backend.main", ...args], repoRoot);
  }
}

function stopBackendIfRunning() {
  if (!backendProcess) {
    return;
  }
  try {
    backendProcess.kill();
  } catch {
    // ignore
  }
  backendProcess = null;
  if (backendLogStream) {
    backendLogStream.end();
    backendLogStream = null;
  }
}

function createWindow() {
  const window = new BrowserWindow({
    width: 1480,
    height: 960,
    minWidth: 1100,
    minHeight: 760,
    backgroundColor: "#f7f7f8",
    autoHideMenuBar: true,
    title: "PC Orchestrator",
    webPreferences: {
      preload: path.join(__dirname, "preload.mjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  const devUrl = process.env.ELECTRON_START_URL || "http://127.0.0.1:5173";
  const productionIndex = path.join(__dirname, "..", "dist", "index.html");

  if (!app.isPackaged) {
    void window.loadURL(devUrl);
    window.webContents.openDevTools({ mode: "detach" });
    return;
  }

  void window.loadFile(productionIndex);
}

app.whenReady().then(() => {
  startBackend();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("before-quit", () => {
  stopBackendIfRunning();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
