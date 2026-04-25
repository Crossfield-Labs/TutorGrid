import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("desktopShell", {
  platform: process.platform,
  pickFiles: async (options = {}) => {
    const result = await ipcRenderer.invoke("desktop:pick-files", options);
    return Array.isArray(result) ? result : [];
  },
});
