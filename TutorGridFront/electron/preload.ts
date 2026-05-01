import { contextBridge, ipcRenderer } from "electron";

const api = {
  app: {
    getInfo: () => ipcRenderer.invoke("app:getInfo"),
  },
  workspace: {
    pickFolder: () => ipcRenderer.invoke("workspace:pickFolder"),
    getRoot: () => ipcRenderer.invoke("workspace:getRoot"),
    setRoot: (newRoot: string) =>
      ipcRenderer.invoke("workspace:setRoot", newRoot),
    loadTiles: () => ipcRenderer.invoke("workspace:loadTiles"),
    saveTiles: (data: unknown) =>
      ipcRenderer.invoke("workspace:saveTiles", data),
    importFile: (payload: { buffer: Uint8Array; originalName: string }) =>
      ipcRenderer.invoke("workspace:importFile", payload),
    listRootFiles: () => ipcRenderer.invoke("workspace:listRootFiles"),
    fileExists: (relPath: string) =>
      ipcRenderer.invoke("workspace:fileExists", relPath),
    readFileBuffer: (relPath: string) =>
      ipcRenderer.invoke("workspace:readFileBuffer", relPath),
    readText: (relPath: string) =>
      ipcRenderer.invoke("workspace:readText", relPath),
    writeText: (payload: { relPath: string; content: string }) =>
      ipcRenderer.invoke("workspace:writeText", payload),
    createHyperdoc: (initialContent?: string) =>
      ipcRenderer.invoke("workspace:createHyperdoc", initialContent ?? ""),
    deleteFile: (relPath: string) =>
      ipcRenderer.invoke("workspace:deleteFile", relPath),
    openExternal: (relPath: string) =>
      ipcRenderer.invoke("workspace:openExternal", relPath),
  },
  window: {
    minimize: () => ipcRenderer.invoke("window:minimize"),
    toggleMaximize: () =>
      ipcRenderer.invoke("window:toggleMaximize") as Promise<boolean>,
    close: () => ipcRenderer.invoke("window:close"),
    isMaximized: () =>
      ipcRenderer.invoke("window:isMaximized") as Promise<boolean>,
    onMaximizedChanged: (cb: (maximized: boolean) => void) => {
      const listener = (_: unknown, value: boolean) => cb(value);
      ipcRenderer.on("window:maximizedChanged", listener);
      return () => ipcRenderer.off("window:maximizedChanged", listener);
    },
  },
};

contextBridge.exposeInMainWorld("metaAgent", api);
