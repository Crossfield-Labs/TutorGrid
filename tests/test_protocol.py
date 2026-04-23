from __future__ import annotations

import unittest

from backend.server.protocol import OrchestratorRequest, build_event


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
        self.assertEqual(request.params.limit, 200)

    def test_request_parsing_reads_history_params(self) -> None:
        request = OrchestratorRequest.from_dict(
            {
                "type": "req",
                "method": "orchestrator.session.history",
                "sessionId": "session-1",
                "params": {"limit": 25, "cursor": "cursor-1"},
            }
        )

        self.assertEqual(request.session_id, "session-1")
        self.assertEqual(request.params.limit, 25)
        self.assertEqual(request.params.cursor, "cursor-1")

    def test_request_parsing_reads_memory_config_params(self) -> None:
        request = OrchestratorRequest.from_dict(
            {
                "type": "req",
                "method": "orchestrator.config.set",
                "params": {
                    "memoryEnabled": True,
                    "memoryAutoCompact": True,
                    "memoryCompactOnComplete": True,
                    "memoryCompactOnFailure": False,
                    "memoryRetrievalScope": "session",
                    "memoryRetrievalStrength": "aggressive",
                    "memoryCleanupEnabled": True,
                    "memoryCleanupIntervalHours": 12,
                },
            }
        )

        self.assertTrue(request.params.memory_enabled)
        self.assertTrue(request.params.memory_auto_compact)
        self.assertFalse(request.params.memory_compact_on_failure)
        self.assertEqual(request.params.memory_retrieval_scope, "session")
        self.assertEqual(request.params.memory_retrieval_strength, "aggressive")
        self.assertEqual(request.params.memory_cleanup_interval_hours, 12)

    def test_request_parsing_reads_push_and_profile_params(self) -> None:
        request = OrchestratorRequest.from_dict(
            {
                "type": "req",
                "method": "orchestrator.profile.get",
                "params": {
                    "pushEnabled": True,
                    "pushOnSessionComplete": True,
                    "pushOnSessionFailure": False,
                    "profileLevel": "L4",
                    "profileKey": "workspace-key",
                },
            }
        )

        self.assertTrue(request.params.push_enabled)
        self.assertTrue(request.params.push_on_session_complete)
        self.assertFalse(request.params.push_on_session_failure)
        self.assertEqual(request.params.profile_level, "L4")
        self.assertEqual(request.params.profile_key, "workspace-key")

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

