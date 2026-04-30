import type {
  AgentData,
  AiBlockKind,
  FlashcardItem,
  QuizQuestion,
} from "./ai-block-types";

export interface MockResolveContext {
  command: string;
  selectionText: string;
}

export interface MockResolution {
  kind: Exclude<AiBlockKind, "placeholder">;
  data: Record<string, any>;
}

const escapeHtml = (s: string) =>
  s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

const explainHtml = (sel: string) => `
  <p>关于「<strong>${escapeHtml(sel) || "该内容"}</strong>」的讲解：</p>
  <ul>
    <li>核心思想是把<strong>关键概念</strong>解释清楚，并把它和你已经学过的内容连接起来。</li>
    <li>常见易错点是<em>把它当成万能锤</em>，记住它的适用边界。</li>
    <li>建议用一个最小例子上手感受。</li>
  </ul>
  <p class="text-medium-emphasis"><em>（这是 Phase 2 占位内容，Phase 3 会替换为后端真实流式输出）</em></p>
`.trim();

const summarizeHtml = (sel: string) => `
  <p><strong>一句话总结：</strong>${escapeHtml(sel) ? escapeHtml(sel).slice(0, 40) : "该内容"} 是关于…的核心阐述。</p>
  <p>三点要点：</p>
  <ol>
    <li>第一要点。</li>
    <li>第二要点。</li>
    <li>第三要点。</li>
  </ol>
`.trim();

const rewriteHtml = (sel: string) => `
  <p>改写版本：</p>
  <blockquote>${escapeHtml(sel) || "（请先选中要改写的文本）"}</blockquote>
  <p>语气更克制、结构更清晰、术语更准确。</p>
`.trim();

const continueHtml = () => `
  <p>承接上文继续展开：补充背景、给出例子、并指出与下一节的衔接点。</p>
  <p>（Phase 2 mock 占位）</p>
`.trim();

const askHtml = (sel: string) => `
  <p>关于「${escapeHtml(sel) || "该问题"}」的回答：</p>
  <p>这里会是 AI 的直接回答，Phase 3 接 WS 后是流式内容。</p>
`.trim();

const ragHtml = (sel: string) => `
  <p>知识库答案：</p>
  <p>${escapeHtml(sel) || "该问题"} 在课程资料中的相关说明大致是…</p>
  <p class="text-medium-emphasis"><em>引用：design-patterns.pdf · 第 12 页（Phase 4 接真正 RAG）</em></p>
`.trim();

const quizQuestions = (sel: string): QuizQuestion[] => [
  {
    question: `下列关于「${sel || "该主题"}」的描述，哪一项最准确？`,
    options: [
      "它定义对象之间的一对多依赖关系",
      "它是一种排序算法",
      "它只能用于前端框架",
      "它和 SQL 强相关",
    ],
    answer: 0,
    explanation: "教材定义：当主题状态变化时，所有观察者都会被通知。",
  },
  {
    question: "在该结构中，下列哪个角色负责发布事件？",
    options: ["Subject", "Observer", "Mediator", "Adapter"],
    answer: 0,
    explanation: "Subject 维护观察者列表并广播变更。",
  },
];

const flashcards = (sel: string): FlashcardItem[] => [
  {
    front: sel || "该概念是什么？",
    back: "用一句话回答：核心思想 + 适用场景 + 一个例子。",
  },
  {
    front: "和最相近的概念有什么区别？",
    back: "对比维度：意图、参与角色、耦合方向。",
  },
  {
    front: "什么时候不该用它？",
    back: "性能敏感、关系简单、生命周期不一致时不必硬上。",
  },
];

const agentData = (sel: string): AgentData => {
  const now = Date.now();
  const isML =
    /机器学习|深度学习|分类|训练|模型|sklearn|MNIST|随机森林|神经网络|实验报告/i.test(
      sel
    );
  if (isML) {
    return {
      task: "用 sklearn 在 MNIST 上训练随机森林分类器，输出准确率与混淆矩阵，并生成报告",
      currentPhase: "starting",
      history: [
        { phase: "created", message: "会话已创建", timestamp: now - 1200 },
        { phase: "starting", message: "Agent 启动，加载 codex 工作器", timestamp: now - 600 },
      ],
      awaitingPrompt: "",
      artifacts: [],
      finalAnswer: "",
      done: false,
    };
  }
  return {
    task: sel ? `基于选区执行：${sel.slice(0, 20)}…` : "执行用户任务",
    currentPhase: "planning",
    history: [
      { phase: "created", message: "会话已创建", timestamp: now - 2400 },
      { phase: "starting", message: "Agent 启动", timestamp: now - 1800 },
      { phase: "planning", message: "正在规划步骤…", timestamp: now - 600 },
    ],
    awaitingPrompt: "",
    artifacts: [],
    finalAnswer: "",
    done: false,
  };
};

const ML_TIMELINE = [
  { phase: "planning", message: "拆解任务：数据加载 → 模型训练 → 评估 → 出报告" },
  { phase: "delegating", message: "委派 codex：写 Python 数据加载与 8:2 划分代码" },
  { phase: "delegating", message: "codex 输出 train_split.py，开始执行" },
  { phase: "inspecting", message: "数据准备完成（60000 训练 + 10000 测试）" },
  { phase: "delegating", message: "委派 codex：构建 RandomForestClassifier，n_estimators=100" },
  { phase: "verifying", message: "训练耗时 18.4s，开始评估" },
  { phase: "verifying", message: "测试集准确率 96.78%，生成混淆矩阵 PNG" },
  { phase: "delegating", message: "委派 codex：用 markdown 写实验报告主文档" },
  { phase: "verifying", message: "pandoc 把 .md 转成 .pdf" },
];

const ML_FINAL_ANSWER = `实验任务已完成。

✓ 在 MNIST 数据集上完成手写数字识别模型训练与评估。
✓ 模型：RandomForestClassifier (n_estimators=100, max_depth=20)
✓ 训练 / 测试集划分：8 : 2
✓ 测试集准确率：96.78%
✓ 混淆矩阵已生成（confusion_matrix.png）
✓ 实验报告已生成（machine_learning_report.md / .pdf）

主要发现：模型对数字 4 与 9 的混淆率最高（约 1.8%），手写差异较小。建议增加这两类的样本量或改用 CNN。`;

const ML_ARTIFACTS = [
  {
    path: "outputs/machine_learning_report.pdf",
    title: "machine_learning_report.pdf",
    summary: "实验报告（PDF 版，含混淆矩阵）",
  },
  {
    path: "outputs/machine_learning_report.md",
    title: "machine_learning_report.md",
    summary: "实验报告（Markdown 源）",
  },
  {
    path: "outputs/confusion_matrix.png",
    title: "confusion_matrix.png",
    summary: "10×10 混淆矩阵热力图",
  },
  {
    path: "outputs/train_split.py",
    title: "train_split.py",
    summary: "数据加载与划分脚本",
  },
  {
    path: "outputs/train_rf.py",
    title: "train_rf.py",
    summary: "随机森林训练与评估脚本",
  },
];

export function resolveMockBlock(ctx: MockResolveContext): MockResolution {
  const sel = ctx.selectionText || "";
  switch (ctx.command) {
    case "explain-selection":
      return { kind: "text", data: { html: explainHtml(sel) } };
    case "summarize-selection":
      return { kind: "text", data: { html: summarizeHtml(sel) } };
    case "rewrite-selection":
      return { kind: "text", data: { html: rewriteHtml(sel) } };
    case "continue-writing":
      return { kind: "text", data: { html: continueHtml() } };
    case "ask":
      return { kind: "text", data: { html: askHtml(sel) } };
    case "rag-query":
      return { kind: "text", data: { html: ragHtml(sel) } };
    case "generate-quiz":
      return { kind: "quiz", data: { questions: quizQuestions(sel) } };
    case "generate-flashcards":
      return { kind: "flashcard", data: { cards: flashcards(sel) } };
    case "do-task":
      return { kind: "agent", data: agentData(sel) };
    default:
      return { kind: "text", data: { html: askHtml(sel) } };
  }
}

export function mockAgentProgress(
  baseData: AgentData,
  step: number
): AgentData {
  const now = Date.now();
  const isML = /MNIST|RandomForest|sklearn|准确率|混淆矩阵|实验报告|机器学习/.test(
    baseData.task || ""
  );
  if (isML) {
    const next = ML_TIMELINE[step] || null;
    if (!next) {
      return {
        ...baseData,
        currentPhase: "completed",
        finalAnswer: ML_FINAL_ANSWER,
        done: true,
        history: [
          ...(baseData.history || []),
          { phase: "completed", message: "全部任务完成", timestamp: now },
        ],
        artifacts: ML_ARTIFACTS,
      };
    }
    return {
      ...baseData,
      currentPhase: next.phase,
      history: [
        ...(baseData.history || []),
        { phase: next.phase, message: next.message, timestamp: now },
      ],
    };
  }
  const progressions = [
    { phase: "inspecting", message: "查阅相关资料 list_files、read_file…" },
    { phase: "delegating", message: "委派给 worker 执行子任务…" },
    {
      phase: "awaiting_user",
      message: "需要你确认任务方向。",
      awaitingPrompt: "我打算从概念→例子→反例的顺序展开，可以吗？",
    },
  ];
  const next = progressions[step] || null;
  if (!next) {
    return {
      ...baseData,
      currentPhase: "completed",
      finalAnswer: "任务已完成（mock）。",
      done: true,
      history: [
        ...(baseData.history || []),
        { phase: "completed", message: "任务结束", timestamp: now },
      ],
      artifacts: [
        {
          path: "hyperdocs/sample-output.md",
          title: "sample-output.md",
          summary: "Agent 生成的产物（mock）",
        },
      ],
    };
  }
  return {
    ...baseData,
    currentPhase: next.phase,
    awaitingPrompt: next.awaitingPrompt || "",
    history: [
      ...(baseData.history || []),
      { phase: next.phase, message: next.message, timestamp: now },
    ],
  };
}

const MOCK_RAG_ANSWER = `根据资料中的描述，**观察者模式**（Observer Pattern）的核心思想可以概括为三点：

1. **一对多依赖**：定义对象之间的一对多依赖关系，使得一个被观察对象（Subject）状态改变时，所有依赖它的观察者（Observer）都会自动收到通知并被更新。
2. **解耦发布与订阅**：被观察者只需要知道观察者实现了某个接口，无需关心观察者的具体类型，从而把"何时通知"和"通知后做什么"解耦。
3. **支持广播通信**：一个事件可以被多个观察者同时响应，每个观察者独立执行自己的更新逻辑。

它常见于事件系统、UI 框架的数据绑定、消息中间件等场景。`;

const MOCK_RAG_CHUNKS = [
  {
    chunkId: "chunk_demo_1",
    fileId: "demo_observer_md",
    fileName: "observer_pattern.md",
    content:
      "Observer 模式定义对象间一对多依赖关系，主题状态改变时，所有依赖对象都会得到通知并被自动更新。它把发布者和订阅者解耦，是事件驱动系统的基础。",
    sourcePage: 1,
    score: 0.91,
  },
  {
    chunkId: "chunk_demo_2",
    fileId: "demo_observer_md",
    fileName: "observer_pattern.md",
    content:
      "实现要点：Subject 维护 observer 列表，提供 attach/detach 接口；Observer 实现 update 方法。注意避免循环依赖与重复通知。",
    sourcePage: 2,
    score: 0.84,
  },
  {
    chunkId: "chunk_demo_3",
    fileId: "demo_design_patterns_pdf",
    fileName: "design_patterns_overview.pdf",
    content:
      "观察者模式与发布订阅的差异：观察者直接持有被观察者引用，发布订阅通过中介解耦。两者都支持广播，但耦合粒度不同。",
    sourcePage: 7,
    score: 0.78,
  },
];

export function mockRagResolution(question: string) {
  return {
    answer: MOCK_RAG_ANSWER,
    chunks: MOCK_RAG_CHUNKS,
    question,
  };
}
