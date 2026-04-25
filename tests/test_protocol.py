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
                    "langsmithEnabled": True,
                    "langsmithProject": "pc-orchestrator-tests",
                    "langsmithApiKey": "ls-key",
                    "langsmithApiUrl": "https://api.smith.langchain.com",
                },
            }
        )

        self.assertTrue(request.params.memory_enabled)
        self.assertTrue(request.params.memory_auto_compact)
        self.assertFalse(request.params.memory_compact_on_failure)
        self.assertEqual(request.params.memory_retrieval_scope, "session")
        self.assertEqual(request.params.memory_retrieval_strength, "aggressive")
        self.assertEqual(request.params.memory_cleanup_interval_hours, 12)
        self.assertTrue(request.params.langsmith_enabled)
        self.assertEqual(request.params.langsmith_project, "pc-orchestrator-tests")
        self.assertEqual(request.params.langsmith_api_key, "ls-key")
        self.assertEqual(request.params.langsmith_api_url, "https://api.smith.langchain.com")

    def test_request_parsing_reads_tiptap_params(self) -> None:
        request = OrchestratorRequest.from_dict(
            {
                "type": "req",
                "method": "orchestrator.tiptap.command",
                "params": {
                    "commandName": "explain-selection",
                    "selectionText": "manacher algorithm",
                    "documentText": "full document text",
                    "execute": True,
                },
            }
        )

        self.assertEqual(request.params.command_name, "explain-selection")
        self.assertEqual(request.params.selection_text, "manacher algorithm")
        self.assertEqual(request.params.document_text, "full document text")
        self.assertTrue(request.params.execute)

    def test_request_parsing_reads_push_and_legacy_profile_params(self) -> None:
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

    def test_request_parsing_reads_knowledge_params(self) -> None:
        request = OrchestratorRequest.from_dict(
            {
                "type": "req",
                "method": "orchestrator.knowledge.file.ingest",
                "params": {
                    "courseId": "course-1",
                    "courseName": "software architecture",
                    "courseDescription": "exam review",
                    "filePath": "D:/data/chapter1.pptx",
                    "fileName": "chapter1.pptx",
                    "chunkSize": 1024,
                    "batchSize": 48,
                },
            }
        )
        self.assertEqual(request.params.course_id, "course-1")
        self.assertEqual(request.params.course_name, "software architecture")
        self.assertEqual(request.params.course_description, "exam review")
        self.assertEqual(request.params.file_path, "D:/data/chapter1.pptx")
        self.assertEqual(request.params.file_name, "chapter1.pptx")
        self.assertEqual(request.params.chunk_size, 1024)
        self.assertEqual(request.params.batch_size, 48)

    def test_request_parsing_reads_learning_profile_params(self) -> None:
        request = OrchestratorRequest.from_dict(
            {
                "type": "req",
                "method": "orchestrator.profile.l4.upsert",
                "params": {
                    "userId": "user-1",
                    "courseId": "course-1",
                    "knowledgePoint": "observer-pattern",
                    "mastery": 0.42,
                    "confidence": 0.9,
                    "lastPracticedAt": "2026-04-22T08:00:00+08:00",
                    "profileData": {
                        "evidence": ["quiz-1 wrong", "lab-review needed"],
                        "notes": "Need to revisit dispatch flow.",
                    },
                },
            }
        )
        self.assertEqual(request.params.user_id, "user-1")
        self.assertEqual(request.params.course_id, "course-1")
        self.assertEqual(request.params.knowledge_point, "observer-pattern")
        self.assertAlmostEqual(request.params.mastery, 0.42)
        self.assertAlmostEqual(request.params.confidence, 0.9)
        self.assertEqual(request.params.last_practiced_at, "2026-04-22T08:00:00+08:00")
        self.assertEqual(request.params.profile_data["notes"], "Need to revisit dispatch flow.")

    def test_build_event_preserves_payload(self) -> None:
        event = build_event(
            event="orchestrator.session.completed",
            task_id="task-1",
            node_id="node-1",
            session_id="session-1",
            payload={"result": "ok"},
            seq=3,
        )

        self.assertEqual(event["type"], "event")
        self.assertEqual(event["event"], "orchestrator.session.completed")
        self.assertEqual(event["payload"], {"result": "ok"})
        self.assertEqual(event["seq"], 3)
        self.assertTrue(event["timestamp"])


if __name__ == "__main__":
    unittest.main()
