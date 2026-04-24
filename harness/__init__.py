from __future__ import annotations

from harness.evaluator import evaluate_harness_result
from harness.models import HarnessEvaluation, HarnessResult, HarnessTaskSpec


def run_task_file(*args, **kwargs):
    from harness.runner import run_task_file as _run_task_file

    return _run_task_file(*args, **kwargs)

__all__ = [
    "HarnessEvaluation",
    "HarnessResult",
    "HarnessTaskSpec",
    "evaluate_harness_result",
    "run_task_file",
]
