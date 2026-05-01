import { Node, mergeAttributes } from "@tiptap/core";
import { VueNodeViewRenderer } from "@tiptap/vue-3";
import AiBlockDispatcher from "./ai-views/AiBlockDispatcher.vue";
import {
  AI_BLOCK_DEFAULT_ATTRS,
  makeAiBlockId,
  type AiBlockAttrs,
  type AiBlockKind,
} from "./ai-block-types";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    aiBlock: {
      insertAiBlock: (attrs: Partial<AiBlockAttrs>) => ReturnType;
      updateAiBlockById: (id: string, attrs: Partial<AiBlockAttrs>) => ReturnType;
      removeAiBlockById: (id: string) => ReturnType;
    };
  }
}

const parseJsonAttr = (value: unknown): Record<string, any> => {
  if (typeof value !== "string" || !value) return {};
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
};

export const AiBlock = Node.create({
  name: "aiBlock",
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,
  isolating: true,

  addAttributes() {
    return {
      id: {
        default: "",
        parseHTML: (el) => (el as HTMLElement).getAttribute("data-id") || "",
        renderHTML: (attrs) => ({ "data-id": attrs.id }),
      },
      kind: {
        default: "placeholder" as AiBlockKind,
        parseHTML: (el) =>
          ((el as HTMLElement).getAttribute("data-kind") as AiBlockKind) ||
          "placeholder",
        renderHTML: (attrs) => ({ "data-kind": attrs.kind }),
      },
      sessionId: {
        default: null,
        parseHTML: (el) =>
          (el as HTMLElement).getAttribute("data-session-id") || null,
        renderHTML: (attrs) =>
          attrs.sessionId ? { "data-session-id": attrs.sessionId } : {},
      },
      command: {
        default: null,
        parseHTML: (el) =>
          (el as HTMLElement).getAttribute("data-command") || null,
        renderHTML: (attrs) =>
          attrs.command ? { "data-command": attrs.command } : {},
      },
      createdBy: {
        default: "ai",
        parseHTML: (el) =>
          (el as HTMLElement).getAttribute("data-created-by") || "ai",
        renderHTML: (attrs) => ({ "data-created-by": attrs.createdBy }),
      },
      createdAt: {
        default: 0,
        parseHTML: (el) => {
          const raw = (el as HTMLElement).getAttribute("data-created-at");
          return raw ? Number(raw) : 0;
        },
        renderHTML: (attrs) => ({
          "data-created-at": String(attrs.createdAt || 0),
        }),
      },
      data: {
        default: {},
        parseHTML: (el) =>
          parseJsonAttr((el as HTMLElement).getAttribute("data-data")),
        renderHTML: (attrs) => ({
          "data-data": JSON.stringify(attrs.data || {}),
        }),
      },
      userState: {
        default: {},
        parseHTML: (el) =>
          parseJsonAttr((el as HTMLElement).getAttribute("data-user-state")),
        renderHTML: (attrs) => ({
          "data-user-state": JSON.stringify(attrs.userState || {}),
        }),
      },
    };
  },

  parseHTML() {
    return [{ tag: "ai-block" }];
  },

  renderHTML({ HTMLAttributes }) {
    return ["ai-block", mergeAttributes(HTMLAttributes)];
  },

  addNodeView() {
    return VueNodeViewRenderer(AiBlockDispatcher);
  },

  addCommands() {
    return {
      insertAiBlock:
        (attrs) =>
        ({ chain }) => {
          const merged = {
            ...AI_BLOCK_DEFAULT_ATTRS,
            id: makeAiBlockId(),
            createdAt: Date.now(),
            ...attrs,
          };
          return chain()
            .insertContent({
              type: "aiBlock",
              attrs: merged,
            })
            .run();
        },

      updateAiBlockById:
        (id, attrs) =>
        ({ tr, state, dispatch }) => {
          let target: { pos: number; node: any } | null = null;
          state.doc.descendants((node, pos) => {
            if (target) return false;
            if (node.type.name === "aiBlock" && node.attrs.id === id) {
              target = { pos, node };
              return false;
            }
            return true;
          });
          if (!target) return false;
          if (dispatch) {
            const next = { ...target.node.attrs, ...attrs };
            tr.setNodeMarkup(target.pos, undefined, next);
          }
          return true;
        },

      removeAiBlockById:
        (id) =>
        ({ tr, state, dispatch }) => {
          let target: { pos: number; size: number } | null = null;
          state.doc.descendants((node, pos) => {
            if (target) return false;
            if (node.type.name === "aiBlock" && node.attrs.id === id) {
              target = { pos, size: node.nodeSize };
              return false;
            }
            return true;
          });
          if (!target) return false;
          if (dispatch) {
            tr.delete(target.pos, target.pos + target.size);
          }
          return true;
        },
    };
  },
});
