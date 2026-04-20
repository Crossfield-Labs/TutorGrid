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

修改时注意：
- provider 特定兼容逻辑应留在 provider 内部
- `openai_compat` 当前要求：先有限重试，再短时熔断；连续失败时快速失败，避免 runtime 一直阻塞
- 引入新的 provider 类型时，要同步更新本文件

