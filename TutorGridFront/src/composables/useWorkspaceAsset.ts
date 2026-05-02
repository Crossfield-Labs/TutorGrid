/**
 * 把工作区里的相对路径资源（如 .assets/xxx.jpg）通过 Electron IPC 读出来
 * 转成 blob URL，可直接给 <img src> / background-image 用。
 *
 * 支持 3 种值：
 *   - ""              → 返回 fallback
 *   - "http(s)://..." → 直接用（外链）
 *   - "/images/..."   → 直接用（前端 public 目录里的内置图）
 *   - ".assets/..."   → 走 IPC 读 buffer 转 blob URL
 */

import { ref, watch, onUnmounted, type Ref } from "vue";

export function useWorkspaceAsset(
  relPathOrUrl: Ref<string>,
  fsRoot: Ref<string>,
  fallback: string
) {
  const resolved = ref<string>(fallback);
  let lastBlobUrl = "";

  function revoke() {
    if (lastBlobUrl) {
      URL.revokeObjectURL(lastBlobUrl);
      lastBlobUrl = "";
    }
  }

  async function resolve() {
    revoke();
    const value = relPathOrUrl.value;
    if (!value) {
      resolved.value = fallback;
      return;
    }
    // 外链 / public 资源直接用
    if (
      value.startsWith("http://") ||
      value.startsWith("https://") ||
      value.startsWith("/")
    ) {
      resolved.value = value;
      return;
    }
    // 工作区内相对资源（.assets/xxx）→ IPC 读 → blob URL
    if (!fsRoot.value || !window.metaAgent?.workspace) {
      resolved.value = fallback;
      return;
    }
    try {
      const buf = await window.metaAgent.workspace.readAssetFrom({
        targetRoot: fsRoot.value,
        relPath: value,
      });
      if (!buf) {
        resolved.value = fallback;
        return;
      }
      const blob = new Blob([buf]);
      lastBlobUrl = URL.createObjectURL(blob);
      resolved.value = lastBlobUrl;
    } catch (err) {
      console.warn("[useWorkspaceAsset] read failed, fallback:", err);
      resolved.value = fallback;
    }
  }

  watch([relPathOrUrl, fsRoot], resolve, { immediate: true });

  onUnmounted(revoke);

  return resolved;
}
