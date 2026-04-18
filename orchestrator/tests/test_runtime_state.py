from orchestrator.runtime.state import create_initial_state


def test_create_initial_state_sets_task_and_goal() -> None:
    state = create_initial_state(
        session_id="s1",
        task_id="t1",
        node_id="n1",
        workspace=".",
        task="task",
        goal="goal",
        max_iterations=4,
    )
    assert state["task"] == "task"
    assert state["goal"] == "goal"
    assert state["max_iterations"] == 4
