from __future__ import annotations

import unittest

from backend.server import app
from backend.sessions.state import OrchestratorSessionState


class ServerArtifactProjectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_emit_projection_updates_broadcasts_structured_artifact_events(self) -> None:
        session = OrchestratorSessionState(
            task_id="task-1",
            node_id="node-1",
            runner="orchestrator",
            workspace=".",
            task="inspect",
            goal="inspect",
        )
        session.latest_artifact_summary = "生成了 1 个学习卡片"
        session.artifacts.append("artifacts/lesson.md")
        session.worker_runs.append(
            {
                "worker": "codex",
                "artifacts": [
                    {"path": "artifacts/lesson.md", "change_type": "created", "size": 256},
                ],
            }
        )

        captured: list[tuple[str, dict[str, object]]] = []
        original_broadcast = app._broadcast_event

        async def _capture(session_arg, *, event: str, payload=None):
            captured.append((event, payload or {}))

        app._broadcast_event = _capture
        try:
            await app._emit_projection_updates(session)
        finally:
            app._broadcast_event = original_broadcast

        event_names = [name for name, _payload in captured]
        self.assertIn("orchestrator.session.artifact.created", event_names)
        self.assertIn("orchestrator.session.tile", event_names)

        tile_payload = next(payload for name, payload in captured if name == "orchestrator.session.tile")
        self.assertEqual(tile_payload["tiles"][0]["path"], "artifacts/lesson.md")
        self.assertEqual(tile_payload["tiles"][0]["changeType"], "created")


if __name__ == "__main__":
    unittest.main()
