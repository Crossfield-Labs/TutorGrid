# 过渡或待清理目录

当前仍然存在，但不属于长期独立架构目标的目录：
- `adapters/`
- `backend/graph/`
- `backend/state/`
- 其他仅用于早期 bootstrap 的残留目录

使用原则：
- 不要继续在这些目录里堆新功能
- 默认把它们视为后续清理对象
- 如果某个目录后面重新变成正式模块，要从本文件移除，并补进 `harness/docs/README.md`

