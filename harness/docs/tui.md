# TUI 模块说明

## 模块定位

`tui/` 是终端形态的轻量客户端，和 GUI 并存，主要用于：

- 后端 WebSocket 协议联调
- 运行中问题排查（phase/summary/await_user）
- CI 或远程环境下的快速验证入口

它不是替代 `frontend/` 的主产品界面。

## 当前入口

- [main.py](D:\works\pc_orchestrator_core\tui\main.py)
- [client.py](D:\works\pc_orchestrator_core\tui\client.py)

启动方式：

```powershell
python -m tui.main --ws-url ws://127.0.0.1:3210/ws/orchestrator
```

## 支持命令

- `/new <task>`：新建会话任务
- `/snapshot`：请求当前会话快照
- `/explain`：请求解释
- `/quit`：退出
- 普通文本：自动路由为 `instruction` 或 `reply`（依据 `awaitingInput`）

## 维护约束

- TUI 只消费稳定协议，不直接依赖 `backend/runtime` 内部实现
- 与 GUI 的协议行为保持一致，避免出现第二套语义
- 若新增 `orchestrator.session.*` 方法，优先同步 TUI 的最小调用路径
