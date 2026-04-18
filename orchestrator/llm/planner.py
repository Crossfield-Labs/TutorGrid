from __future__ import annotations

from typing import Any

from orchestrator.config import OrchestratorConfig
from orchestrator.llm.messages import deserialize_messages, serialize_messages
from orchestrator.llm.prompts import build_planner_prompt
from orchestrator.providers.registry import ProviderRegistry


class PlannerRuntime:
    def __init__(self, config: OrchestratorConfig) -> None:
        self.config = config
        self.prompt = build_planner_prompt()
        self.provider = ProviderRegistry.create(config.planner)

    def build_messages(self, *, task: str, goal: str, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.prompt is None:
            return history
        langchain_messages = self.prompt.format_messages(
            goal=goal or task,
            task=task,
            history=deserialize_messages(history),
        )
        return serialize_messages(langchain_messages)
