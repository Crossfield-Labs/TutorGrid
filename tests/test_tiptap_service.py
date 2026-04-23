from __future__ import annotations

import unittest

from backend.editor.tiptap import TipTapAICommandService


class TipTapServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TipTapAICommandService()

    def test_explain_selection_command_builds_learning_task(self) -> None:
        result = self.service.resolve(
            command_name="explain-selection",
            selection_text="马拉车算法用于在线性时间内求最长回文子串。",
            document_text="",
            instruction_text="",
        )

        self.assertEqual(result.command_name, "explain-selection")
        self.assertIn("讲解这段内容", result.task)
        self.assertIn("马拉车算法", result.task)

    def test_rewrite_selection_uses_instruction_text(self) -> None:
        result = self.service.resolve(
            command_name="rewrite-selection",
            selection_text="原始内容",
            document_text="",
            instruction_text="改成更适合教学讲义的风格",
        )

        self.assertIn("改成更适合教学讲义的风格", result.task)
        self.assertIn("原始内容", result.task)


if __name__ == "__main__":
    unittest.main()
