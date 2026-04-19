import { app, BrowserWindow } from "electron";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

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
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
