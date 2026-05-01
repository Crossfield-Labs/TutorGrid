from __future__ import annotations

import unittest

from backend.llm.messages import (
    append_assistant_message,
    append_tool_message,
    deserialize_messages,
    serialize_messages,
)


class LLMMessageSerializationTests(unittest.TestCase):
    def test_roundtrip_preserves_assistant_tool_calls_before_tool_messages(self) -> None:
        history = []
        append_assistant_message(
            history,
            content="",
            tool_calls=[
                {
                    "id": "call-list-files",
                    "type": "function",
                    "function": {
                        "name": "list_files",
                        "arguments": '{"path": "."}',
                    },
                }
            ],
        )
        append_tool_message(
            history,
            tool_call_id="call-list-files",
            tool_name="list_files",
            result="- FILE observer.md",
        )

        roundtrip = serialize_messages(deserialize_messages(history))

        self.assertEqual(roundtrip[0]["role"], "assistant")
        self.assertEqual(roundtrip[0]["tool_calls"][0]["id"], "call-list-files")
        self.assertEqual(roundtrip[0]["tool_calls"][0]["function"]["name"], "list_files")
        self.assertEqual(roundtrip[1]["role"], "tool")
        self.assertEqual(roundtrip[1]["tool_call_id"], "call-list-files")


if __name__ == "__main__":
    unittest.main()
