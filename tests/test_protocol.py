from __future__ import annotations

import unittest

from server.protocol import OrchestratorRequest, build_event


class ProtocolTests(unittest.TestCase):
    def test_request_parsing_uses_defaults(self) -> None:
        request = OrchestratorRequest.from_dict(
            {
                "type": "req",
                "method": "orchestrator.session.start",
                "id": "req-1",
                "taskId": "task-1",
                "nodeId": "node-1",
                "params": {"task": "inspect repo"},
            }
        )

        self.assertEqual(request.type, "req")
        self.assertEqual(request.method, "orchestrator.session.start")
        self.assertEqual(request.request_id, "req-1")
        self.assertEqual(request.params.runner, "orchestrator")
        self.assertEqual(request.params.input_intent, "reply")
        self.assertEqual(request.params.task, "inspect repo")

    def test_build_event_preserves_payload(self) -> None:
        event = build_event(
            event="orchestrator.session.completed",
            task_id="task-1",
            node_id="node-1",
            session_id="session-1",
            payload={"result": "ok"},
        )

        self.assertEqual(event["type"], "event")
        self.assertEqual(event["event"], "orchestrator.session.completed")
        self.assertEqual(event["payload"], {"result": "ok"})


if __name__ == "__main__":
    unittest.main()
