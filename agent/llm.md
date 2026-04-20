# LLM 模块

主要代码：
- `backend/llm/planner.py`
- `backend/llm/prompts.py`
- `backend/llm/messages.py`

职责：
- 定义 LangChain 侧的 prompt 和 message 层
- 给 runtime 提供 planner 能力

关键点：
- LangChain 在这里主要承担组件层角色
- prompt、message、模型交互负载的组织放在这里
- runtime 决定什么时候调用 planner，这个模块决定如何组织调用内容

修改时注意：
- prompt 构造与 runtime 状态流转分开
- message 序列化要稳定、可逆
- 不要把传输层细节塞进这个模块

