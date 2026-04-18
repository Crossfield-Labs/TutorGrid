# MetaAgent PC Orchestrator

> PC 端子调度 Agent —— MetaAgent 系统的计算机侧执行中枢

## 项目定位

PC Orchestrator 是 MetaAgent 体系中的 **PC 子调度 Agent**。它不是一个简单的远程命令执行器，而是一个具备自主规划能力的子 Agent 运行时：

```
用户 → Android 主 Agent（主编排树）→ PC 子 Agent（本项目）→ 具体 Worker（Claude / Codex / OpenCode / Shell）
```

- **Android 端**是主调度器，负责任务理解、主编排树、用户交互
- **PC 端**是子调度 Agent，接收 Android 的执行请求后，自主选择 Worker、规划执行步骤、流式回传进度
- **Worker** 是具体的执行后端（Claude Agent SDK / Codex CLI / OpenCode CLI / Shell）

通信方式：**WebSocket 长连接 + 事件流**（不是 HTTP 请求响应）

---

## 当前实现状态

### ✅ 已完成（Step 1 + Step 2 + 部分 Step 3）

| 模块 | 状态 | 说明 |
|------|------|------|
| WebSocket Server | ✅ 完整 | 监听 `ws://host:port/ws/pc-agent`，Token 鉴权，Session 订阅/广播 |
| 协议层 | ✅ 完整 | 请求解析 (`PcSessionRequest`)、事件构建 (`build_event`) |
| Session 管理 | ✅ 完整 | 创建/更新/查询、线程安全锁、Worker 控制挂载、Follow-up 队列 |
| Session 状态机 | ✅ 完整 | IDLE→STARTING→RUNNING→AWAIT_USER→RUNNING→COMPLETED/FAILED/CANCELLED |
| 会话快照 | ✅ 完整 | 带版本号的 snapshot 系统，差量投影更新 |
| Session Trace | ✅ 完整 | JSONL 格式追踪日志写入 `scratch/session-trace/` |
| Runner Router | ✅ 完整 | 路由到 shell / claude_cli / codex_cli / pc_subagent |
| Shell Runner | ✅ 完整 | PowerShell 执行、UTF-8/GBK 多编码、用户确认机制 |
| Claude CLI Runner | ✅ 完整 | Claude CLI 子进程管道模式 |
| Codex Runner | ✅ 完整 | 委托给 CodexWorker |
| **PC SubAgent Runtime** | ✅ **核心** | **LLM 驱动的自主规划循环**，迭代式 tool-calling |
| LLM Provider | ✅ 完整 | OpenAI 兼容 API 客户端，重试 + 指数退避 |
| Provider Registry | ✅ 完整 | 工厂模式创建 Provider |
| Sub-Agent 工具集 | ✅ 完整 | list_files / read_file / run_shell / web_fetch / await_user / delegate_agent / delegate_opencode |
| Worker 选择策略 | ✅ 完整 | 基于任务关键词自动选 Worker + Session Mode + Profile |
| Claude SDK Worker | ✅ **深度集成** | claude-agent-sdk 完整接入：Session new/resume/fork、Profile 权限规则、Hook 系统、Interrupt、MCP 状态、工作区快照差分 |
| Codex Worker | ✅ 完整 | Codex CLI JSON 事件流解析、Session resume、工作区差分 |
| OpenCode Worker | ✅ 完整 | OpenCode CLI JSON 事件流解析、工作区差分 |
| Worker 自动 Fallback | ✅ 完整 | 一个 Worker 失败自动切换到下一个候选 |
| 中途等待用户输入 | ✅ 完整 | `await_user` 机制 + `pc.session.await_user` 事件 |
| Follow-up 消息队列 | ✅ 完整 | 运行中接受追加输入，支持 redirect/chat intent |
| Interrupt 支持 | ✅ 完整 | Claude Worker 支持实时中断 |
| 配置系统 | ✅ 完整 | 环境变量优先 + JSON 文件兜底 |
| Dev CLI | ✅ 完整 | `python -m subagent.dev_cli` 独立测试 |

### ❌ 未实现

| 模块 | 说明 |
|------|------|
| Event Bus | `events/event_bus.py` 未实现，只有空的 `ProgressEvent` 模型 |
| 状态持久化 | 无 SQLite/JSON state store，Session 全在内存，重启丢失 |
| Session Pause/Resume | `pc.session.pause` / `pc.session.resume` 协议未处理 |
| dialogue.message / dialogue.reply | 主聊天侧信道协议未实现 |
| 断线重连 / 恢复 | WebSocket 断开后无法恢复已有 Session |
| Local Runner | `runners/local_runner.py` 未实现 |
| Browser Runner | 未实现 |
| Report Builder | 未实现 |
| Dify Runner | 未实现 |
| LangGraph 集成 | 按设计延后，未实现 |
| WinUI 3 桌面壳 | 未实现 |
| utils 公共模块 | `utils/logging.py`、`utils/subprocess_stream.py` 未实现 |

### 📁 参考代码（非本项目）

| 目录 | 说明 |
|------|------|
| `MAAMCP/` | MAA-MCP 参考项目（已 gitignore） |
| `nanobot/` | NanoBot 参考项目 |
| `Test/` / `Test2/` | 历史测试产物 |

---

## 项目结构

```
pc_orchestrator/
├── main.py                          # 入口：启动 WebSocket 服务
├── requirements.txt                 # 依赖：httpx, websockets, claude-agent-sdk
├── PC_子Agent_渐进开发方案.md         # 设计文档
│
├── server/                          # WebSocket 服务层
│   ├── app.py                       # 核心服务：连接管理、事件广播、Session 生命周期
│   └── protocol.py                  # 协议模型：PcSessionRequest, build_event
│
├── sessions/                        # Session 管理
│   ├── session_manager.py           # SessionManager：CRUD + Worker 控制 + Follow-up 队列
│   └── session_state.py             # PcSessionState：状态机 + 快照 + 历史
│
├── router/                          # Runner 路由
│   └── runner_router.py             # RunnerRouter：按名称路由到具体 Runner
│
├── runners/                         # Runner 层（Session → 执行）
│   ├── base.py                      # BaseRunner 抽象基类
│   ├── shell_runner.py              # PowerShell 直接执行
│   ├── claude_runner.py             # Claude CLI 管道模式（简单版）
│   ├── codex_runner.py              # 委托给 CodexWorker
│   └── pc_subagent_runner.py        # 委托给 PcSubAgentRuntime（核心）
│
├── subagent/                        # ⭐ PC 子 Agent 运行时（核心大脑）
│   ├── runtime.py                   # PcSubAgentRuntime：LLM 驱动的迭代规划循环
│   ├── context_builder.py           # System prompt + 消息历史构建
│   ├── models.py                    # RuntimeState, SubstepRecord
│   ├── tool_registry.py             # 工具注册表
│   ├── tool_base.py                 # SubAgentTool 抽象基类
│   ├── dev_cli.py                   # 独立测试 CLI
│   └── capabilities/                # 子 Agent 可用工具
│       ├── filesystem.py            # list_files, read_file
│       ├── shell.py                 # run_shell
│       ├── web.py                   # web_fetch
│       ├── user_prompt.py           # await_user
│       ├── opencode.py              # delegate_opencode
│       └── agent_delegate.py        # delegate_agent（智能多 Worker 委托）
│
├── workers/                         # Worker 后端适配层
│   ├── base.py                      # WorkerAdapter 抽象基类
│   ├── models.py                    # WorkerResult, WorkerProgressEvent, WorkerControlRef 等
│   ├── registry.py                  # WorkerRegistry：注册 opencode/codex/claude
│   ├── selection.py                 # 智能选择：Worker / Session Mode / Profile
│   ├── claude_sdk_worker.py         # Claude Agent SDK 深度集成（796 行）
│   ├── claude_sdk_bridge.py         # Claude SDK 消息翻译桥
│   ├── codex_worker.py              # Codex CLI 集成
│   └── opencode_worker.py           # OpenCode CLI 集成
│
├── providers/                       # LLM Provider 层
│   ├── base.py                      # LLMProvider, LLMResponse, ToolCallRequest
│   ├── openai_compat.py             # OpenAI 兼容 API 客户端
│   └── registry.py                  # ProviderRegistry 工厂
│
├── config/                          # 配置
│   ├── subagent_config.py           # SubAgentConfig：环境变量 + JSON 双源
│   └── subagent_config.example.json # 配置示例
│
├── events/                          # 事件模型（骨架）
│   └── event_models.py              # ProgressEvent（仅模型，无 Bus）
│
└── scratch/                         # 运行时产物（gitignore）
    └── session-trace/               # Session JSONL 追踪日志
```

---

## 环境要求

- **Python 3.11+**（使用了 `slots=True` dataclass、`X | Y` 类型语法）
- **Windows**（Shell Runner 硬编码调用 PowerShell）
- **可选 CLI 工具**（按需安装）：
  - `claude` — Claude Code CLI（用于 Claude CLI Runner 和 Claude SDK Worker）
  - `codex` — OpenAI Codex CLI
  - `opencode` — OpenCode CLI
  - `claude-agent-sdk` — Claude Agent SDK Python 包

---

## 配置

### 方式一：环境变量（推荐）

在 PowerShell 中设置：

```powershell
# ===== 必填：子 Agent 规划器（LLM）配置 =====
$env:METAAGENT_SUBAGENT_PROVIDER="openai_compat"
$env:METAAGENT_SUBAGENT_MODEL="gpt-5.4"
$env:METAAGENT_SUBAGENT_API_BASE="https://api.vveai.com/v1"
$env:METAAGENT_SUBAGENT_API_KEY="sk-TO917e****5cF5"

# ===== 可选：Worker CLI 路径 =====
$env:METAAGENT_SUBAGENT_CODEX_COMMAND="codex"
$env:METAAGENT_SUBAGENT_OPENCODE_COMMAND="opencode"
$env:METAAGENT_SUBAGENT_CLAUDE_COMMAND="claude"

# ===== 可选：调优参数 =====
$env:METAAGENT_SUBAGENT_TEMPERATURE="0.2"
$env:METAAGENT_SUBAGENT_MAX_TOKENS="4096"
$env:METAAGENT_SUBAGENT_MAX_ITERATIONS="16"
$env:METAAGENT_SUBAGENT_SHELL_TIMEOUT="90"

# ===== 可选：Claude SDK 高级配置 =====
$env:METAAGENT_SUBAGENT_CLAUDE_SDK_ENABLED="true"
$env:METAAGENT_SUBAGENT_CLAUDE_PERMISSION_MODE="acceptEdits"
$env:METAAGENT_SUBAGENT_CLAUDE_PROFILE="code"
$env:METAAGENT_SUBAGENT_CLAUDE_ENABLE_INTERRUPT="true"
$env:METAAGENT_SUBAGENT_CLAUDE_ENABLE_HOOKS="true"
```

### 方式二：JSON 配置文件

复制 `config/subagent_config.example.json` 为 `config/subagent_config.json`：

```json
{
  "planner": {
    "provider": "openai_compat",
    "model": "gpt-5.4",
    "apiKey": "sk-TO917e****5cF5",
    "apiBase": "https://api.vveai.com/v1",
    "temperature": 0.2,
    "maxTokens": 4096
  },
  "maxIterations": 16,
  "shellTimeoutSeconds": 90,
  "codexCommand": "codex",
  "opencodeCommand": "opencode",
  "claudeCommand": "claude",
  "claudeSdkEnabled": true,
  "claudePermissionMode": "acceptEdits",
  "claudeProfileDefault": "code",
  "claudeEnableInterrupt": true,
  "claudeEnableHooks": true
}
```

> **优先级**：环境变量 > JSON 文件 > 硬编码默认值

### 全部环境变量清单

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `METAAGENT_SUBAGENT_PROVIDER` | `openai_compat` | LLM Provider 类型 |
| `METAAGENT_SUBAGENT_MODEL` | (空) | 模型名称 |
| `METAAGENT_SUBAGENT_API_BASE` | (空) | API 基础 URL |
| `METAAGENT_SUBAGENT_API_KEY` | (空) | API Key |
| `METAAGENT_SUBAGENT_TEMPERATURE` | `0.2` | 生成温度 |
| `METAAGENT_SUBAGENT_MAX_TOKENS` | `4096` | 最大 token 数 |
| `METAAGENT_SUBAGENT_MAX_ITERATIONS` | `16` | 子 Agent 最大迭代次数 |
| `METAAGENT_SUBAGENT_SHELL_TIMEOUT` | `90` | Shell 命令超时秒数 |
| `METAAGENT_SUBAGENT_CODEX_COMMAND` | `codex` | Codex CLI 可执行文件 |
| `METAAGENT_SUBAGENT_CODEX_MODEL` | (空) | Codex 使用的模型 |
| `METAAGENT_SUBAGENT_OPENCODE_COMMAND` | `opencode` | OpenCode CLI 可执行文件 |
| `METAAGENT_SUBAGENT_OPENCODE_MODEL` | (空) | OpenCode 使用的模型 |
| `METAAGENT_SUBAGENT_OPENCODE_AGENT` | (空) | OpenCode agent 参数 |
| `METAAGENT_SUBAGENT_CLAUDE_COMMAND` | `claude` | Claude CLI 可执行文件 |
| `METAAGENT_SUBAGENT_CLAUDE_MODEL` | (空) | Claude 使用的模型 |
| `METAAGENT_SUBAGENT_CLAUDE_SDK_ENABLED` | `true` | 是否启用 Claude Agent SDK |
| `METAAGENT_SUBAGENT_CLAUDE_PERMISSION_MODE` | `acceptEdits` | Claude 权限模式 |
| `METAAGENT_SUBAGENT_CLAUDE_PROFILE` | `code` | Claude 默认 profile |
| `METAAGENT_SUBAGENT_CLAUDE_ENABLE_INTERRUPT` | `true` | 是否允许中断 Claude |
| `METAAGENT_SUBAGENT_CLAUDE_ENABLE_HOOKS` | `true` | 是否启用 Claude Hooks |
| `METAAGENT_SUBAGENT_CLAUDE_ENABLE_SESSION_INTROSPECTION` | `true` | 是否启用会话内省 |
| `METAAGENT_SUBAGENT_CLAUDE_SETTINGS` | (空) | Claude settings.json 路径 |
| `METAAGENT_SUBAGENT_CLAUDE_MCP_CONFIG` | (空) | Claude MCP 配置路径 |
| `METAAGENT_SUBAGENT_CLAUDE_ALLOWED_TOOLS` | (空) | 允许的 Claude 工具（逗号分隔） |
| `METAAGENT_SUBAGENT_CLAUDE_DISALLOWED_TOOLS` | (空) | 禁止的 Claude 工具（逗号分隔） |

---

## 启动

### 1. 安装依赖

```powershell
cd d:\SoftInnovationCompetition\Projects\MetaAgent\pc_orchestrator
pip install -r requirements.txt
```

### 2. 设置环境变量

```powershell
$env:METAAGENT_SUBAGENT_PROVIDER="openai_compat"
$env:METAAGENT_SUBAGENT_MODEL="gpt-5.4"
$env:METAAGENT_SUBAGENT_API_BASE="https://api.vveai.com/v1"
$env:METAAGENT_SUBAGENT_API_KEY="sk-TO917e****5cF5"
$env:METAAGENT_SUBAGENT_CODEX_COMMAND="codex"
```

### 3. 启动服务

```powershell
# 默认监听 0.0.0.0:3210
python main.py

# 自定义端口和 Token
python main.py --host 0.0.0.0 --port 3210 --token "your-secret-token"
```

启动成功后输出：
```
MetaAgent PC Orchestrator listening on ws://0.0.0.0:3210/ws/pc-agent
```

### 4. 独立测试子 Agent（不需要 Android）

```powershell
python -m subagent.dev_cli "检查当前目录结构并总结" --workspace "D:\your\project"
```

---

## WebSocket 连接

### 连接地址

```
ws://<PC_IP>:3210/ws/pc-agent
```

### 鉴权

如果启动时指定了 `--token`，客户端需要在请求头中带上：

```
X-MetaAgent-Token: your-secret-token
```

### Android 端连接注意事项

- PC 端必须用 `--host 0.0.0.0`（不能是 `127.0.0.1`）
- Android 和 PC 必须在同一局域网
- Android 填写的地址是 PC 的局域网 IP（如 `ws://192.168.1.100:3210/ws/pc-agent`）
- Token 必须一致
- 路径必须是 `/ws/pc-agent`

---

## WebSocket 协议

### Android → PC（请求）

所有请求格式：
```json
{
  "type": "req",
  "method": "pc.session.xxx",
  "taskId": "...",
  "nodeId": "...",
  "sessionId": "...",
  "params": { ... }
}
```

| 方法 | 说明 | 关键 params |
|------|------|-------------|
| `pc.session.start` | 开始新会话 | `runner`, `workspace`, `task`, `goal`, `command` |
| `pc.session.input` | 向会话发送输入 | `text`, `inputIntent`(reply/chat/redirect/interrupt/explain), `target` |
| `pc.session.snapshot` | 请求当前快照 | (无) |
| `pc.session.interrupt` | 中断当前 Worker | `text` |
| `pc.session.cancel` | 取消会话 | (无) |

### PC → Android（事件）

所有事件格式：
```json
{
  "type": "event",
  "event": "pc.session.xxx",
  "taskId": "...",
  "nodeId": "...",
  "sessionId": "...",
  "payload": { ... }
}
```

| 事件 | 说明 |
|------|------|
| `pc.session.started` | 会话已创建并开始执行 |
| `pc.session.progress` | 流式进度更新 |
| `pc.session.await_user` | 等待用户输入 |
| `pc.session.subnode.started` | 子步骤开始 |
| `pc.session.subnode.completed` | 子步骤完成 |
| `pc.session.completed` | 会话完成（含 result） |
| `pc.session.failed` | 会话失败（含 error） |
| `pc.session.phase` | 阶段变更 |
| `pc.session.worker` | Worker 变更 |
| `pc.session.summary` | 摘要更新 |
| `pc.session.artifact_summary` | 产物摘要更新 |
| `pc.session.snapshot` | 完整快照推送 |
| `pc.session.followup.accepted` | Follow-up 输入已接受 |
| `pc.session.permission` | 权限状态变更 |
| `pc.session.mcp_status` | MCP 状态变更 |
| `pc.session.worker_runtime` | Worker 运行时信息变更 |

### Runner 类型

| runner 值 | 说明 |
|-----------|------|
| `shell` | 直接执行 PowerShell 命令 |
| `claude_cli` | 调用 Claude CLI（简单管道模式） |
| `codex_cli` | 调用 Codex CLI |
| `pc_subagent` | **核心模式**：LLM 驱动的自主子 Agent，自动选择和切换 Worker |

---

## 核心架构：pc_subagent Runner

当 runner 为 `pc_subagent` 时，系统进入最核心的模式：

```
Android 发送 pc.session.start (runner=pc_subagent)
    → PcSubAgentRunner
        → PcSubAgentRuntime（LLM 规划循环）
            → LLM Provider（OpenAI 兼容 API）决定下一步行动
            → 调用工具：
                ├── list_files / read_file  → 检查工作区
                ├── run_shell               → 执行 Shell 命令
                ├── web_fetch               → 抓取网页内容
                ├── await_user              → 等待用户输入
                └── delegate_agent          → 委托给 Worker 后端
                    ├── 自动选择 Worker（opencode / codex / claude）
                    ├── 自动选择 Session Mode（new / resume / fork）
                    ├── 自动选择 Profile（code / doc / study / research）
                    ├── 执行并收集结果
                    └── 失败时自动 Fallback 到下一个候选 Worker
            → 循环直到得到最终答案或达到迭代上限
```

### Worker 选择逻辑

| 任务特征 | 优先 Worker | 原因 |
|---------|-------------|------|
| 含"implement/write/create/fix/edit" | opencode | 面向具体代码生成/编辑 |
| 含"review/analyze/inspect/explain" | codex | 面向代码审查/分析 |
| 含"document/report/research/study" | claude | 面向文档/研究/学习 |
| 明确指定 worker 名称 | 指定的 worker | 用户意图优先 |
| 一个失败 | 自动切到下一个 | Fallback 机制 |

### Claude Profile 规则

| Profile | 允许的工具 | 禁止的工具 | 适用场景 |
|---------|-----------|-----------|---------|
| `code` | Read/Write/Edit/LS/Glob/Grep/Bash | (无) | 代码实现 |
| `doc` | Read/Write/Edit/LS/Glob/Grep | Bash | 文档编写 |
| `study` | Read/Write/Edit/LS/Glob/Grep | Bash | 学习/教学 |
| `research` | Read/Write/Edit/LS/Glob/Grep/WebFetch/WebSearch | Bash | 研究/调研 |

---

## 快速测试示例

### 用 wscat 手动测试

```powershell
# 安装 wscat
npm install -g wscat

# 连接
wscat -c ws://127.0.0.1:3210/ws/pc-agent
```

发送 Shell 任务：
```json
{"type":"req","method":"pc.session.start","taskId":"test-1","nodeId":"n1","params":{"runner":"shell","workspace":"D:/your/project","task":"列出当前目录结构"}}
```

发送 SubAgent 任务（核心模式）：
```json
{"type":"req","method":"pc.session.start","taskId":"test-2","nodeId":"n2","params":{"runner":"pc_subagent","workspace":"D:/your/project","task":"检查这个项目的代码结构，总结主要模块功能"}}
```

向等待中的会话发送输入：
```json
{"type":"req","method":"pc.session.input","sessionId":"abc123","params":{"text":"继续执行","inputIntent":"reply"}}
```

请求当前快照：
```json
{"type":"req","method":"pc.session.snapshot","sessionId":"abc123"}
```

---

## 关键未开发项说明

### 1. 状态持久化（影响：高）
当前所有 Session 存在内存中，服务重启即丢失。需要实现 `sessions/state_store.py`（SQLite 或 JSON 文件）。

### 2. 断线重连（影响：高）
WebSocket 断开后，Android 无法恢复已有的 Session。需要实现 Session 恢复机制。

### 3. Event Bus（影响：中）
`events/event_bus.py` 未实现，当前事件直接在 `app.py` 中硬编码分发。解耦后更利于扩展。

### 4. Pause/Resume 协议（影响：中）
`pc.session.pause` / `pc.session.resume` 在设计文档中定义但未实现。

### 5. dialogue 侧信道（影响：低）
`dialogue.message` / `dialogue.reply` 未实现，当前 Android 与 PC 只能通过 Session 事件通信。

---

## 依赖说明

`requirements.txt`:
```
httpx>=0.27,<1
websockets>=12,<16
claude-agent-sdk>=0.1.52
```

- `httpx` — HTTP 客户端（当前代码中 Provider 实际使用 `urllib`，httpx 备用）
- `websockets` — WebSocket 服务端
- `claude-agent-sdk` — Claude Agent SDK（可选，若不用 Claude SDK Worker 可不装）
