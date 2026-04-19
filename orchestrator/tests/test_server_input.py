from __future__ import annotations

import unittest

from orchestrator.server.app import _classify_input_handling


class ServerInputTests(unittest.TestCase):
    def test_reply_requires_waiter(self) -> None:
        self.assertEqual(_classify_input_handling(input_intent="reply", waiter_active=True), "reply_waiter")
        self.assertEqual(_classify_input_handling(input_intent="reply", waiter_active=False), "reply_without_waiter")

    def test_redirect_queues_even_when_waiting(self) -> None:
        self.assertEqual(_classify_input_handling(input_intent="redirect", waiter_active=True), "queue_followup")
        self.assertEqual(_classify_input_handling(input_intent="instruction", waiter_active=False), "queue_followup")

    def test_explain_and_interrupt_are_special_actions(self) -> None:
        self.assertEqual(_classify_input_handling(input_intent="explain", waiter_active=False), "explain")
        self.assertEqual(_classify_input_handling(input_intent="interrupt", waiter_active=True), "interrupt")
