# Agent Architecture

## Components

- `backend/agent/main_agent.py`: Copilot-style chat agent orchestration.
- `backend/agent/tools.py`: tool definitions and execution.
- `backend/rag/service.py`: course knowledge retrieval and citation generation.
- Tavily: external web search for fresh information.

## Tool Routing

- Course-scoped questions: prefer `rag_query`.
- Time-sensitive or "latest" questions: prefer `tavily_search`.
- If no tool is suitable: answer directly with LLM.
