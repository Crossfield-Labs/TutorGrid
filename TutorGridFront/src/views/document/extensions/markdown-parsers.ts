import type { FlashcardItem, QuizQuestion } from "./ai-block-types";

const OPTION_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H"];

function letterToIndex(letter: string): number {
  const up = letter.trim().toUpperCase();
  const idx = OPTION_LETTERS.indexOf(up);
  return idx >= 0 ? idx : -1;
}

function stripMarkdownInline(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/__(.+?)__/g, "$1")
    .replace(/\*(.+?)\*/g, "$1")
    .replace(/_(.+?)_/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .trim();
}

interface RawQuizBlock {
  question: string;
  options: { letter?: string; text: string }[];
  answer?: string;
  explanation?: string;
}

function splitIntoBlocks(md: string): string[] {
  const lines = md.split(/\r?\n/);
  const blocks: string[] = [];
  let buf: string[] = [];
  const startPattern =
    /^(?:#{1,6}\s+(?:题目|问题|Question|Q)[\s\d.:：]*|(?:\*\*)?(?:题目|问题|Question|Q)\s*\d+|(\d+)[.)、])/i;
  for (const line of lines) {
    if (startPattern.test(line) && buf.length > 0) {
      blocks.push(buf.join("\n"));
      buf = [line];
    } else {
      buf.push(line);
    }
  }
  if (buf.length > 0) blocks.push(buf.join("\n"));
  return blocks.filter((b) => b.trim().length > 0);
}

function parseSingleQuizBlock(block: string): RawQuizBlock | null {
  const lines = block
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0);
  if (lines.length === 0) return null;

  const optionRegex = /^[-*•·]?\s*\(?([A-Ha-h])\)?[.、:：）)\s]+(.+)$/;
  const answerRegex =
    /^(?:\*{0,2})?(?:答案|正确答案|Answer|A)(?:\*{0,2})?\s*[:：]\s*\(?([A-Ha-h0-9])\)?/i;
  const explRegex =
    /^(?:\*{0,2})?(?:解析|解释|Explanation|Reasoning)(?:\*{0,2})?\s*[:：]\s*(.+)$/i;
  const questionLeadRegex =
    /^#{1,6}\s+|^(?:\*\*)?(?:题目|问题|Question|Q)\s*\d*[\s.:：]*|^\d+[.)、]\s*/i;

  const options: { letter: string; text: string }[] = [];
  let questionParts: string[] = [];
  let answer = "";
  let explanation = "";
  let phase: "question" | "options" | "answer" | "explanation" = "question";

  for (const line of lines) {
    const optMatch = optionRegex.exec(line);
    if (optMatch) {
      options.push({
        letter: optMatch[1].toUpperCase(),
        text: stripMarkdownInline(optMatch[2]),
      });
      phase = "options";
      continue;
    }
    const ansMatch = answerRegex.exec(line);
    if (ansMatch) {
      answer = ansMatch[1].toUpperCase();
      phase = "answer";
      continue;
    }
    const explMatch = explRegex.exec(line);
    if (explMatch) {
      explanation = stripMarkdownInline(explMatch[1]);
      phase = "explanation";
      continue;
    }
    if (phase === "explanation") {
      explanation += " " + stripMarkdownInline(line);
      continue;
    }
    if (phase === "question") {
      const cleaned = line.replace(questionLeadRegex, "").trim();
      if (cleaned) questionParts.push(stripMarkdownInline(cleaned));
    }
  }

  const question = questionParts.join(" ").trim();
  if (!question || options.length < 2) return null;
  return { question, options, answer, explanation };
}

export function parseQuizMarkdown(md: string): QuizQuestion[] {
  if (!md || !md.trim()) return [];
  const blocks = splitIntoBlocks(md);
  const result: QuizQuestion[] = [];
  for (const block of blocks) {
    const raw = parseSingleQuizBlock(block);
    if (!raw) continue;
    const answerIdx = raw.answer
      ? /\d/.test(raw.answer)
        ? Math.max(0, parseInt(raw.answer, 10) - 1)
        : letterToIndex(raw.answer)
      : -1;
    result.push({
      question: raw.question,
      options: raw.options.map((o) => o.text),
      answer: answerIdx >= 0 && answerIdx < raw.options.length ? answerIdx : 0,
      explanation: raw.explanation || undefined,
    });
  }
  return result;
}

const FRONT_LABELS = /^(?:正面|问|Q|Front|Question)\s*[:：]\s*(.+)$/i;
const BACK_LABELS = /^(?:反面|答|A|Back|Answer)\s*[:：]\s*(.+)$/i;
const NUMBERED = /^\d+[.)、]\s*(.+)$/;

export function parseFlashcardMarkdown(md: string): FlashcardItem[] {
  if (!md || !md.trim()) return [];
  const lines = md.split(/\r?\n/);
  const cards: FlashcardItem[] = [];

  let pendingFront = "";
  let pendingBack = "";
  const flush = () => {
    const front = stripMarkdownInline(pendingFront);
    const back = stripMarkdownInline(pendingBack);
    if (front && back) cards.push({ front, back });
    pendingFront = "";
    pendingBack = "";
  };

  let lastFilled: "front" | "back" | null = null;
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      if (pendingFront && pendingBack) flush();
      continue;
    }
    if (/^[-*=]{3,}$/.test(line)) {
      if (pendingFront && pendingBack) flush();
      continue;
    }
    const f = FRONT_LABELS.exec(line);
    if (f) {
      if (pendingFront && pendingBack) flush();
      pendingFront = f[1];
      lastFilled = "front";
      continue;
    }
    const b = BACK_LABELS.exec(line);
    if (b) {
      pendingBack = b[1];
      lastFilled = "back";
      continue;
    }
    const n = NUMBERED.exec(line);
    if (n && !pendingFront) {
      pendingFront = n[1];
      lastFilled = "front";
      continue;
    }
    if (lastFilled === "front") {
      pendingFront = pendingFront ? `${pendingFront} ${line}` : line;
    } else if (lastFilled === "back") {
      pendingBack = pendingBack ? `${pendingBack} ${line}` : line;
    } else if (!pendingFront) {
      pendingFront = line;
      lastFilled = "front";
    } else {
      pendingBack = pendingBack ? `${pendingBack} ${line}` : line;
      lastFilled = "back";
    }
  }
  if (pendingFront && pendingBack) flush();
  return cards;
}

export function markdownToSimpleHtml(md: string): string {
  if (!md) return "";
  const escape = (s: string) =>
    s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

  const lines = md.split(/\r?\n/);
  const out: string[] = [];
  let inList: "ul" | "ol" | null = null;
  let inCode = false;
  let codeBuf: string[] = [];
  let paraBuf: string[] = [];

  const closeList = () => {
    if (inList) {
      out.push(`</${inList}>`);
      inList = null;
    }
  };
  const flushPara = () => {
    if (paraBuf.length === 0) return;
    const text = paraBuf.join(" ");
    const html = renderInline(text);
    out.push(`<p>${html}</p>`);
    paraBuf = [];
  };

  const renderInline = (s: string): string => {
    let r = escape(s);
    r = r.replace(/`([^`]+)`/g, "<code>$1</code>");
    r = r.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    r = r.replace(/__(.+?)__/g, "<strong>$1</strong>");
    r = r.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, "<em>$1</em>");
    r = r.replace(/(?<!_)_([^_]+)_(?!_)/g, "<em>$1</em>");
    r = r.replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noreferrer">$1</a>'
    );
    return r;
  };

  for (const raw of lines) {
    const line = raw.replace(/\s+$/g, "");
    if (line.startsWith("```")) {
      if (inCode) {
        out.push(`<pre><code>${escape(codeBuf.join("\n"))}</code></pre>`);
        codeBuf = [];
        inCode = false;
      } else {
        flushPara();
        closeList();
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      codeBuf.push(raw);
      continue;
    }
    if (!line.trim()) {
      flushPara();
      closeList();
      continue;
    }
    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    if (heading) {
      flushPara();
      closeList();
      const lvl = heading[1].length;
      out.push(`<h${lvl}>${renderInline(heading[2])}</h${lvl}>`);
      continue;
    }
    const ul = /^[-*+]\s+(.+)$/.exec(line);
    if (ul) {
      flushPara();
      if (inList !== "ul") {
        closeList();
        out.push("<ul>");
        inList = "ul";
      }
      out.push(`<li>${renderInline(ul[1])}</li>`);
      continue;
    }
    const ol = /^\d+[.)]\s+(.+)$/.exec(line);
    if (ol) {
      flushPara();
      if (inList !== "ol") {
        closeList();
        out.push("<ol>");
        inList = "ol";
      }
      out.push(`<li>${renderInline(ol[1])}</li>`);
      continue;
    }
    const bq = /^>\s?(.*)$/.exec(line);
    if (bq) {
      flushPara();
      closeList();
      out.push(`<blockquote>${renderInline(bq[1])}</blockquote>`);
      continue;
    }
    closeList();
    paraBuf.push(line.trim());
  }
  if (inCode) {
    out.push(`<pre><code>${escape(codeBuf.join("\n"))}</code></pre>`);
  }
  flushPara();
  closeList();
  return out.join("\n");
}
