from __future__ import annotations

import unittest

from sessions.state import OrchestratorSessionState


class SessionStateTests(unittest.TestCase):
    def test_followups_are_drained_and_snapshot_exposes_state(self) -> None:
        session = OrchestratorSessionState(
            task_id="task-1",
            node_id="node-1",
            runner="orchestrator",
            workspace=".",
            task="inspect",
            goal="inspect",
        )
        session.followups.append({"text": "continue", "intent": "reply", "target": ""})
        session.request_user_input("Need input", "text")
        session.set_active_worker_runtime(
            worker="codex",
            session_mode="resume",
            task_id="worker-task-1",
            profile="code",
            can_interrupt=True,
        )

        snapshot = session.build_snapshot()
        drained = session.drain_followups()

        self.assertTrue(snapshot["awaitingInput"])
        self.assertEqual(snapshot["activeWorker"], "codex")
        self.assertEqual(snapshot["pendingFollowups"][0]["text"], "continue")
        self.assertEqual(drained[0]["intent"], "reply")
        self.assertEqual(session.followups, [])


if __name__ == "__main__":
    unittest.main()
