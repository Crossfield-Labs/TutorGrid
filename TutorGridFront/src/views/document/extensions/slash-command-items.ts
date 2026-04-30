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

export const SLASH_ITEMS: SlashItem[] = [
  {
    command: "explain-selection",
    title: "讲解",
    subtitle: "讲解上方选中或最近内容",
    icon: "mdi-message-text-outline",
    keywords: ["explain", "讲解", "解释"],
  },
  {
    command: "summarize-selection",
    title: "总结",
    subtitle: "用一句话 + 三点要点总结",
    icon: "mdi-text-short",
    keywords: ["summary", "总结", "概括"],
  },
  {
    command: "rewrite-selection",
    title: "改写",
    subtitle: "重写上方文字",
    icon: "mdi-pencil-outline",
    keywords: ["rewrite", "改写", "润色"],
  },
  {
    command: "continue-writing",
    title: "续写",
    subtitle: "承接上文继续写",
    icon: "mdi-text-long",
    keywords: ["continue", "续写"],
  },
  {
    command: "generate-quiz",
    title: "出测验",
    subtitle: "基于上方内容生成单选题",
    icon: "mdi-help-circle-outline",
    keywords: ["quiz", "测验", "题目"],
  },
  {
    command: "generate-flashcards",
    title: "生成闪卡",
    subtitle: "正反面记忆卡片",
    icon: "mdi-cards-outline",
    keywords: ["flashcard", "闪卡", "记忆"],
  },
  {
    command: "do-task",
    title: "Agent 执行任务",
    subtitle: "把这段当作任务交给 Agent",
    icon: "mdi-robot-outline",
    color: "warning",
    keywords: ["agent", "任务", "执行"],
  },
  {
    command: "rag-query",
    title: "问知识库",
    subtitle: "RAG 检索课程资料",
    icon: "mdi-bookshelf",
    color: "success",
    keywords: ["rag", "知识库", "查询"],
  },
];
