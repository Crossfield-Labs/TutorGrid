from __future__ import annotations

try:
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
except ImportError:  # pragma: no cover
    ChatPromptTemplate = None
    MessagesPlaceholder = None


def build_planner_prompt() -> ChatPromptTemplate | None:
    if ChatPromptTemplate is None or MessagesPlaceholder is None:
        return None
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are the standalone orchestrator runtime built with LangGraph and LangChain.\n"
                    "Goal: {goal}\n"
                    "Plan carefully, prefer tools for evidence, and keep track of runtime state."
                ),
            ),
            MessagesPlaceholder(variable_name="history", optional=True),
            ("human", "{task}"),
        ]
    )
