/**
 * TaskRegisterNode
 *
 * 文档左栏只放一个轻量单行节点："📋 [任务标题] · 状态 · [打开 drawer]"
 * 编排过程的所有可视化都在右侧 OrchestrationDrawer + TaskTile，文档不堆气泡。
 * 节点本身只持有 taskId，状态由 useOrchestratorTaskStore 通过 store 拉取实时同步。
 */

import { Node, mergeAttributes } from "@tiptap/core";
import { VueNodeViewRenderer } from "@tiptap/vue-3";
import TaskRegisterView from "./ai-views/TaskRegister.vue";

export interface TaskRegisterAttrs {
  taskId: string;
  sessionId: string;
  docId: string;
  /** 用户选中的原始片段，仅用于在节点上回显，不参与逻辑 */
  selectionPreview: string;
}

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    taskRegister: {
      insertTaskRegister: (attrs: TaskRegisterAttrs) => ReturnType;
      removeTaskRegisterById: (taskId: string) => ReturnType;
    };
  }
}

export const TaskRegisterNode = Node.create({
  name: "taskRegister",
  group: "block",
  atom: true,
  draggable: false,
  selectable: true,
  defining: true,

  addAttributes() {
    return {
      taskId: { default: "" },
      sessionId: { default: "" },
      docId: { default: "" },
      selectionPreview: { default: "" },
    };
  },

  parseHTML() {
    return [{ tag: "div[data-task-register]" }];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      "div",
      mergeAttributes(HTMLAttributes, { "data-task-register": "true" }),
    ];
  },

  addNodeView() {
    return VueNodeViewRenderer(TaskRegisterView);
  },

  addCommands() {
    return {
      insertTaskRegister:
        (attrs) =>
        ({ commands }) => {
          const ok = commands.insertContent([
            { type: "taskRegister", attrs },
            { type: "paragraph" },
          ]);
          if (!ok) {
            console.warn("[TaskRegisterNode] insertContent failed", attrs);
          }
          return ok;
        },

      removeTaskRegisterById:
        (taskId) =>
        ({ tr, state, dispatch }) => {
          let found = false;
          state.doc.descendants((node, pos) => {
            if (node.type.name === "taskRegister" && node.attrs.taskId === taskId) {
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
