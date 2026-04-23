from __future__ import annotations

from dataclasses import dataclass


def _compact_text(text: str, *, limit: int = 1200) -> str:
    normalized = " ".join(text.split())
    return normalized[:limit]


@dataclass(slots=True)
class TipTapCommand:
    command_name: str
    title: str
    task: str
    selection_text: str
    document_text: str

    def to_payload(self) -> dict[str, str]:
        return {
            "commandName": self.command_name,
            "title": self.title,
            "task": self.task,
            "selectionText": self.selection_text,
            "documentText": self.document_text,
        }


class TipTapAICommandService:
    def resolve(
        self,
        *,
        command_name: str,
        selection_text: str,
        document_text: str,
        instruction_text: str,
    ) -> TipTapCommand:
        normalized_command = (command_name or "ask").strip().lower().replace("_", "-")
        selection = selection_text.strip()
        document = document_text.strip()
        instruction = instruction_text.strip()
        focus_text = selection or document
        compact_focus = _compact_text(focus_text)

        if normalized_command == "explain-selection":
            title = "讲解选中内容"
            task = f"请讲解这段内容，突出关键概念、步骤和易错点：\n{compact_focus}"
        elif normalized_command == "summarize-selection":
            title = "总结选中内容"
            task = f"请总结这段内容，并提炼成 3-5 条学习要点：\n{compact_focus}"
        elif normalized_command == "rewrite-selection":
            title = "改写选中内容"
            rewrite_instruction = instruction or "保持原意但表达更清晰。"
            task = f"请按要求改写这段内容：{rewrite_instruction}\n原文：\n{compact_focus}"
        elif normalized_command == "continue-writing":
            title = "续写当前内容"
            task = f"请基于下面上下文继续写作，风格保持一致：\n{_compact_text(document, limit=1800)}"
        elif normalized_command == "generate-quiz":
            title = "生成测验"
            task = f"请基于下面内容生成一组用于学习检查的题目，并附简短答案：\n{compact_focus}"
        elif normalized_command == "generate-flashcards":
            title = "生成记忆卡片"
            task = f"请基于下面内容生成一组问答式记忆卡片：\n{compact_focus}"
        else:
            title = "处理编辑器内容"
            if instruction:
                task = f"{instruction}\n\n参考内容：\n{compact_focus or _compact_text(document, limit=1800)}"
            else:
                task = f"请根据下面内容给出学习辅助回答：\n{compact_focus or _compact_text(document, limit=1800)}"

        return TipTapCommand(
            command_name=normalized_command,
            title=title,
            task=task.strip(),
            selection_text=selection,
            document_text=document,
        )
