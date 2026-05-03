# AGENTS 指南

这是当前仓库根目录给 agent 使用的总入口文件。

建议阅读顺序：
1. `README.md`：先看项目范围和启动方式
2. `CONTRIBUTING.md`：再看协作和改动约束
3. `docs/persistence.md`：先看持久化模型
4. `docs/BackEndA/orchestrator-v5-protocol.md`：再看 V5 编排协议与任务级事件模型
5. `docs/harness.md`：如果要做任务驱动执行、评测或回归，先看 harness 结构
6. `harness/docs/gaps.md`：最后看当前剩余缺口和框架职责边界
7. `harness/docs/README.md`：按模块导航定位要读的文档
8. `harness/docs/` 下对应模块文档：进入具体代码区域前先读

如何使用 `harness/` 目录：
- 把 `harness/docs/README.md` 当作总导航
- 根据要修改的代码区域读取对应模块文档
- 优先读模块文档，再去扫实现文件
- 当模块边界、行为、协作方式变化时，同步更新对应文档

文档更新规则：
- 小改动：如果只是修改单个模块内部实现，且没有改变模块职责、入口、协议、测试路径，至少更新对应的 `harness/docs/*.md`
- 中等改动：如果改变了模块边界、运行方式、配置方式、验证路径或目录职责，除了对应 `harness/docs/*.md`，还要更新 `harness/docs/README.md`，必要时更新 `harness/docs/gaps.md` 和 `CONTRIBUTING.md`
- 大改动：如果改变了系统结构、根入口、核心执行路径、协议模型、架构方向或协作方式，必须同时更新 `README.md`、`AGENTS.md`、`harness/docs/gaps.md`、相关 `harness/docs/*.md`，并把详细说明补到 `docs/`
- 新增顶层模块：必须更新 `harness/docs/README.md`，并补一份新的模块文档
- 废弃模块或目录：必须更新 `harness/docs/deprecated.md`，如果会影响阅读顺序或协作方式，也要同步更新 `AGENTS.md`
- 不确定时：宁可多更新文档，不要让代码变化和文档描述脱节

对 agent 的要求：
- 保持实现方向与独立重构目标一致
- 不要随意重新依赖仓库外层的旧模块
- 新的 runtime、协议、worker 行为要反映到 `harness/` 文档中
- 新的 harness 任务格式、执行入口、评测方式要反映到 `docs/harness.md` 和 `harness/docs/harness.md`
- 长篇设计说明应放在 `docs/`，而不是堆在本文件里

