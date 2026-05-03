/**
 * 全局 EditorBus（Step 2 跨视图同步基础设施）
 *
 * 用途：让浮窗里的 ChatAssistant（teleport 到 body）能跟当前打开的 TipTap editor 通话：
 *   - ChatAssistant 调 insertAiBubble({ content }) → 文档当前光标插入 AI 节点
 *   - DocumentEditor 调 register(editor, docId) 把自己的 editor 实例挂到 bus
 *
 * 是个轻量"单例 ref"，不引 mitt 之类的库。
 */

import { computed, ref } from "vue";
import type { Editor } from "@tiptap/core";

const activeEditor = ref<Editor | null>(null);
const activeDocId = ref<string>("");

export function useDocumentEditorBus() {
  return {
    /** 当前是否有活跃 editor（浮窗"插入到文档"按钮根据这个显隐）*/
    hasActiveEditor: computed(() => !!activeEditor.value),
    activeDocId: computed(() => activeDocId.value),

    /** DocumentEditor mounted 时调用 */
    register(editor: Editor, docId: string) {
      activeEditor.value = editor;
      activeDocId.value = docId;
    },

    /** DocumentEditor unmount 时调用 */
    unregister(editor?: Editor) {
      if (!editor || activeEditor.value === editor) {
        activeEditor.value = null;
        activeDocId.value = "";
      }
    },

    /**
     * Chat → 文档：在当前光标位置插入一段从 Chat 引用过来的 AI 内容
     * 实现：blockquote 形式（保留语义"这是 AI 引用"，又跟现有 F07 AiBubbleNode 区分）
     * F07 的 AiBubbleNode 是 SSE 直出的活气泡（绑定 messageStore），
     * 这里插入的是已完成的静态引用块。
     */
    insertAiBubble(payload: {
      content: string;
      sourceChatMessageId?: string;
    }) {
      const editor = activeEditor.value;
      if (!editor) return false;
      const text = payload.content || "";
      editor
        .chain()
        .focus()
        .insertContent({
          type: "blockquote",
          content: [
            {
              type: "paragraph",
              content: [{ type: "text", text: `💬 来自 Chat: ${text}` }],
            },
          ],
        })
        .run();
      return true;
    },
  };
}
