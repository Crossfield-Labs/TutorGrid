# Server 模块

主要代码：
- `server/app.py`
- `server/protocol.py`

职责：
- 暴露独立 WebSocket 服务
- 接收 session 生命周期请求
- 广播进度、快照、完成与失败事件

关键点：
- 当前 socket 路径是 `/ws/orchestrator`
- token 校验在 WebSocket 入口完成
- server 暴露的方法应与 runtime 真正支持的能力保持一致

修改时注意：
- 请求解析放在 `protocol.py`
- 订阅、广播、连接行为放在 `app.py`
- 新消息类型要同步反映到 snapshot 和广播逻辑
