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
    // 工作区资源（如背景图）：复制到 <targetRoot>/.assets/，返回相对路径
    saveAssetTo: (payload: {
      targetRoot: string;
      buffer: Uint8Array;
      originalName: string;
    }) => ipcRenderer.invoke("workspace:saveAssetTo", payload) as Promise<{
      relPath: string;
    }>,
    // 读 <targetRoot>/<relPath> 返回 Uint8Array（用 new Blob([buf]) 转 blob URL 显示）
    readAssetFrom: (payload: { targetRoot: string; relPath: string }) =>
      ipcRenderer.invoke("workspace:readAssetFrom", payload) as Promise<
        Uint8Array | null
      >,
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
