# Runners 模块

主要代码：
- `runners/base.py`
- `runners/router.py`
- `runners/subagent_runner.py`

职责：
- 作为 server 请求与 runtime 执行之间的外层抽象
- 根据 session 选择合适的 runner

关键点：
- runner 应该保持轻量
- 真正的执行图属于 `runtime/`
- router 应该可预测、易扩展

修改时注意：
- 不要把重业务逻辑堆进 runner
- 尽量把执行流转逻辑下沉到 `runtime/`
- 保持 callback 形态与 server 的进度/用户输入路径兼容
