import type { SlashItem } from "./SlashCommandMenu.vue";

export function filterSlashItems(
  items: SlashItem[],
  query: string
): SlashItem[] {
  const q = query.trim().toLowerCase();
  if (!q) return items;
  return items.filter((it) => {
    if (it.command.toLowerCase().includes(q)) return true;
    if (it.title.toLowerCase().includes(q)) return true;
    return (it.keywords || []).some((k) => k.toLowerCase().includes(q));
  });
}

/**
 * Slash 命令菜单 = 插入格式块（参考 Notion）
 * AI 操作不放这里，要触发 AI 请选中文字弹出 BubbleMenu
 */
export const SLASH_ITEMS: SlashItem[] = [
  {
    command: "h1",
    title: "标题 1",
    subtitle: "大号章节标题",
    icon: "mdi-format-header-1",
    keywords: ["h1", "title", "标题"],
  },
  {
    command: "h2",
    title: "标题 2",
    subtitle: "中号小节标题",
    icon: "mdi-format-header-2",
    keywords: ["h2"],
  },
  {
    command: "h3",
    title: "标题 3",
    subtitle: "小号子标题",
    icon: "mdi-format-header-3",
    keywords: ["h3"],
  },
  {
    command: "bullet-list",
    title: "无序列表",
    subtitle: "项目符号列表",
    icon: "mdi-format-list-bulleted",
    keywords: ["bullet", "ul", "列表"],
  },
  {
    command: "ordered-list",
    title: "有序列表",
    subtitle: "数字编号列表",
    icon: "mdi-format-list-numbered",
    keywords: ["ordered", "ol", "数字"],
  },
  {
    command: "code-block",
    title: "代码块",
    subtitle: "插入多行代码",
    icon: "mdi-code-tags",
    keywords: ["code", "代码"],
  },
  {
    command: "blockquote",
    title: "引用",
    subtitle: "引用块",
    icon: "mdi-format-quote-open",
    keywords: ["quote", "blockquote", "引用"],
  },
  {
    command: "hr",
    title: "分隔线",
    subtitle: "水平分隔",
    icon: "mdi-minus",
    keywords: ["divider", "hr", "分隔"],
  },
  {
    command: "ask-ai",
    title: "向 AI 提问",
    subtitle: "在光标处插入 AI 气泡，基于上文回答",
    icon: "mdi-sparkles",
    color: "primary",
    keywords: ["ai", "ask", "提问", "气泡"],
  },
  {
    command: "task",
    title: "编排任务",
    subtitle: "发送指令给编排引擎执行多步任务",
    icon: "mdi-cog-sync-outline",
    color: "deep-purple",
    keywords: ["task", "run", "任务", "编排", "执行"],
  },
];
