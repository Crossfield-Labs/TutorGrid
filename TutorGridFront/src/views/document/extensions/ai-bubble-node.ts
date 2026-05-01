/**
 * AiBubbleNode (F07 核心)
 *
 * TipTap 块级节点，把 AI 对话气泡嵌入文档流。
 * 数据来源：messageStore — 一个 bubble = 一对 (userMessageId, aiMessageId)
 * 节点本身只存 id，渲染由 AiBubble.vue 通过 store 拉取实时内容
 */

import { Node, mergeAttributes } from "@tiptap/core";
import { VueNodeViewRenderer } from "@tiptap/vue-3";
import AiBubbleView from "./ai-views/AiBubble.vue";

export interface AiBubbleAttrs {
  sessionId: string;
  userMessageId: string;
  aiMessageId: string;
  command: string;
}

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    aiBubble: {
      insertAiBubble: (attrs: AiBubbleAttrs) => ReturnType;
      removeAiBubbleById: (aiMessageId: string) => ReturnType;
    };
  }
}

export const AiBubbleNode = Node.create({
  name: "aiBubble",
  group: "block",
  atom: true,            // 不可编辑内部 —— 用户改文档不会破坏气泡
  draggable: false,
  selectable: true,
  defining: true,

  addAttributes() {
    return {
      sessionId: { default: "" },
      userMessageId: { default: "" },
      aiMessageId: { default: "" },
      command: { default: "" },
    };
  },

  parseHTML() {
    return [{ tag: "div[data-ai-bubble]" }];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      "div",
      mergeAttributes(HTMLAttributes, { "data-ai-bubble": "true" }),
    ];
  },

  addNodeView() {
    return VueNodeViewRenderer(AiBubbleView);
  },

  addCommands() {
    return {
      insertAiBubble:
        (attrs) =>
        ({ commands }) => {
          // 一次性插入磁贴节点 + 气泡后的空段（光标可继续输入）
          const ok = commands.insertContent([
            { type: "aiBubble", attrs },
            { type: "paragraph" },
          ]);
          if (!ok) {
            console.warn("[AiBubbleNode] insertContent 失败", attrs);
          }
          return ok;
        },

      removeAiBubbleById:
        (aiMessageId) =>
        ({ tr, state, dispatch }) => {
          let found = false;
          state.doc.descendants((node, pos) => {
            if (
              node.type.name === "aiBubble" &&
              node.attrs.aiMessageId === aiMessageId
            ) {
              tr.delete(pos, pos + node.nodeSize);
              found = true;
              return false;
            }
            return true;
          });
          if (found && dispatch) dispatch(tr);
          return found;
        },
    };
  },
});
