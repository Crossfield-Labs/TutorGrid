from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.memory.models import MemoryCompaction, MemoryDocument


@dataclass(slots=True)
class SessionMemoryCompressionResult:
    compaction: MemoryCompaction
    documents: list[MemoryDocument]


class SessionMemoryCompressor:
    def compress_session(
        self,
        *,
        session_id: str,
        task: str,
        goal: str,
        history_items: list[dict[str, Any]],
    ) -> SessionMemoryCompressionResult:
        cleaned_items = [item for item in history_items if not self._is_noise_item(item)]
        summary = self._build_summary(task=task, goal=goal, items=cleaned_items)
        facts = self._build_facts(task=task, goal=goal, items=cleaned_items)
        updated_at = datetime.now(timezone.utc).isoformat()
        compaction = MemoryCompaction(
            session_id=session_id,
            summary=summary,
            facts=facts,
            source_item_count=len(history_items),
            updated_at=updated_at,
        )
        documents = self._build_documents(
            session_id=session_id,
            summary=summary,
            facts=facts,
            items=cleaned_items,
            updated_at=updated_at,
        )
        return SessionMemoryCompressionResult(compaction=compaction, documents=documents)

    def _is_noise_item(self, item: dict[str, Any]) -> bool:
        event = str(item.get("event") or "").strip().lower()
        title = str(item.get("title") or "").strip()
        detail = str(item.get("detail") or "").strip()
        kind = str(item.get("kind") or "").strip().lower()
        if not detail and kind in {"phase", "snapshot"}:
            return True
        if ".subnode." in event and title in {"当前步骤已完成", "正在处理当前步骤", "正在调用执行端", "正在处理中"}:
            return True
        if event.endswith(".progress") and not detail:
            return True
        if event.endswith(".phase") and detail == title:
            return True
        if "accepted user reply" in detail.lower():
            return True
        return False

    def _build_summary(self, *, task: str, goal: str, items: list[dict[str, Any]]) -> str:
        summary_lines = [f"会话任务：{task or goal}".strip()]
        if goal and goal != task:
            summary_lines.append(f"会话目标：{goal}")
        final_items = [
            item for item in items if str(item.get("event") or "").endswith((".completed", ".failed", ".await_user"))
        ]
        if final_items:
            latest = final_items[-1]
            summary_lines.append(f"最近状态：{latest.get('title') or latest.get('event')}")
            detail = str(latest.get("detail") or "").strip()
            if detail:
                summary_lines.append(f"结论：{detail}")
        else:
            important = [str(item.get("detail") or "").strip() for item in items if str(item.get("detail") or "").strip()]
            if important:
                summary_lines.append(f"摘要：{important[-1]}")
        return "\n".join(line for line in summary_lines if line)

    def _build_facts(self, *, task: str, goal: str, items: list[dict[str, Any]]) -> list[str]:
        facts: list[str] = []
        if task:
            facts.append(f"任务：{task}")
        if goal and goal != task:
            facts.append(f"目标：{goal}")
        for item in items:
            detail = str(item.get("detail") or "").strip()
            if not detail:
                continue
            if detail.startswith("{") and detail.endswith("}"):
                continue
            candidate = detail.replace("\n", " ").strip()
            if not candidate or candidate in facts:
                continue
            facts.append(candidate)
            if len(facts) >= 8:
                break
        return facts

    def _build_documents(
        self,
        *,
        session_id: str,
        summary: str,
        facts: list[str],
        items: list[dict[str, Any]],
        updated_at: str,
    ) -> list[MemoryDocument]:
        documents: list[MemoryDocument] = [
            MemoryDocument(
                document_id=f"{session_id}:summary",
                session_id=session_id,
                document_type="session_summary",
                title="会话摘要",
                content=summary,
                metadata={"kind": "summary"},
                token_estimate=max(1, len(summary) // 4),
                created_at=updated_at,
                updated_at=updated_at,
            )
        ]
        if facts:
            facts_text = "\n".join(f"- {fact}" for fact in facts)
            documents.append(
                MemoryDocument(
                    document_id=f"{session_id}:facts",
                    session_id=session_id,
                    document_type="session_facts",
                    title="关键事实",
                    content=facts_text,
                    metadata={"kind": "facts", "factCount": len(facts)},
                    token_estimate=max(1, len(facts_text) // 4),
                    created_at=updated_at,
                    updated_at=updated_at,
                )
            )
        for index, item in enumerate(items[:12], start=1):
            title = str(item.get("title") or item.get("event") or f"片段 {index}").strip() or f"片段 {index}"
            detail = str(item.get("detail") or "").strip()
            if not detail:
                continue
            documents.append(
                MemoryDocument(
                    document_id=f"{session_id}:chunk:{index}",
                    session_id=session_id,
                    document_type="session_chunk",
                    title=title,
                    content=detail,
                    metadata={
                        "kind": item.get("kind") or "event",
                        "event": item.get("event") or "",
                        "createdAt": item.get("createdAt") or "",
                    },
                    token_estimate=max(1, len(detail) // 4),
                    created_at=updated_at,
                    updated_at=updated_at,
                )
            )
        return documents
