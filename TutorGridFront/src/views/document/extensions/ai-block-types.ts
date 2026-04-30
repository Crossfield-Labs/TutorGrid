export type AiBlockKind =
  | "placeholder"
  | "text"
  | "quiz"
  | "flashcard"
  | "agent"
  | "citation";

export interface CitationChunk {
  chunkId?: string;
  fileId?: string;
  fileName?: string;
  content: string;
  sourcePage?: number;
  sourceSection?: string;
  score?: number;
}

export interface CitationData {
  question?: string;
  answer?: string;
  answerHtml?: string;
  courseId?: string;
  courseName?: string;
  chunks?: CitationChunk[];
}

export type AiBlockOriginCommand =
  | "explain-selection"
  | "summarize-selection"
  | "rewrite-selection"
  | "continue-writing"
  | "generate-quiz"
  | "generate-flashcards"
  | "do-task"
  | "rag-query"
  | "ask"
  | string;

export interface PlaceholderData {
  label?: string;
}

export interface TextData {
  html?: string;
  markdown?: string;
}

export interface QuizQuestion {
  question: string;
  options: string[];
  answer: number;
  explanation?: string;
}

export interface QuizData {
  markdown?: string;
  questions?: QuizQuestion[];
}

export interface QuizUserState {
  selected?: Record<number, number>;
  revealed?: boolean;
}

export interface FlashcardItem {
  front: string;
  back: string;
}

export interface FlashcardData {
  markdown?: string;
  cards?: FlashcardItem[];
}

export interface FlashcardUserState {
  index?: number;
  flipped?: Record<number, boolean>;
}

export interface AgentPhaseEvent {
  phase: string;
  message?: string;
  timestamp: number;
}

export interface AgentArtifact {
  path: string;
  title?: string;
  summary?: string;
}

export interface AgentData {
  task?: string;
  currentPhase?: string;
  history?: AgentPhaseEvent[];
  awaitingPrompt?: string;
  artifacts?: AgentArtifact[];
  finalAnswer?: string;
  done?: boolean;
}

export interface AgentUserState {
  draft?: string;
  submitted?: string;
  dismissed?: boolean;
}

export interface AiBlockAttrs {
  id: string;
  kind: AiBlockKind;
  sessionId: string | null;
  command: AiBlockOriginCommand | null;
  createdBy: "ai" | "user";
  createdAt: number;
  data: Record<string, any>;
  userState: Record<string, any>;
}

export const AI_BLOCK_DEFAULT_ATTRS: AiBlockAttrs = {
  id: "",
  kind: "placeholder",
  sessionId: null,
  command: null,
  createdBy: "ai",
  createdAt: 0,
  data: {},
  userState: {},
};

export function makeAiBlockId(): string {
  return `ab_${Date.now().toString(36)}_${Math.random()
    .toString(36)
    .slice(2, 8)}`;
}

export const PLACEHOLDER_LABELS: Record<string, string> = {
  "explain-selection": "正在生成讲解",
  "summarize-selection": "正在总结",
  "rewrite-selection": "正在改写",
  "continue-writing": "正在续写",
  "generate-quiz": "正在出题",
  "generate-flashcards": "正在生成闪卡",
  "do-task": "Agent 正在执行",
  "rag-query": "正在检索知识库",
  "ask": "AI 思考中",
};
