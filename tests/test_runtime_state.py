import unittest

from backend.runtime.state import create_initial_state


class RuntimeStateTests(unittest.TestCase):
    def test_create_initial_state_sets_task_and_goal(self) -> None:
        state = create_initial_state(
            session_id="s1",
            task_id="t1",
            node_id="n1",
            workspace=".",
            task="task",
            goal="goal",
            max_iterations=4,
        )
        self.assertEqual(state["task"], "task")
        self.assertEqual(state["goal"], "goal")
        self.assertEqual(state["max_iterations"], 4)


