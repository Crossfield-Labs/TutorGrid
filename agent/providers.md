# Providers 模块

主要代码：
- `backend/providers/base.py`
- `backend/providers/registry.py`
- `backend/providers/openai_compat.py`

职责：
- 用统一接口抽象模型 provider
- 隔离 API 兼容与 HTTP 细节

关键点：
- provider 选择逻辑放在 registry
- 请求/响应格式转换放在具体 provider
- runtime 与 planner 应依赖抽象接口，而不是底层 HTTP 细节
- 网络抖动、429、5xx、TLS 中断等不稳定问题，应优先在 provider 层做重试与熔断，而不是在前端掩盖
- `ProviderRegistry` 现在会把常见国产 provider 名称（如 `qwen`、`deepseek`、`glm`、`moonshot`、`kimi`、`dashscope`、`siliconflow`）统一归到 `openai_compat`
- 国产模型别名和兼容选项通过 `PlannerConfig.provider_options` 控制，支持：
  - `model_aliases`
  - `extra_body`
  - `extra_headers`

修改时注意：
- provider 特定兼容逻辑应留在 provider 内部
- `openai_compat` 当前要求：先有限重试，再短时熔断；连续失败时快速失败，避免 runtime 一直阻塞
- 常见国产模型的默认别名应保持“保守且可覆盖”，不要把业务判断散落到 runtime
- 引入新的 provider 类型时，要同步更新本文件

