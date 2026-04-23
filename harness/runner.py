from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from harness.evaluator import evaluate_harness_result
from harness.models import HarnessBatchSummary, HarnessResult, HarnessTaskSpec
from websockets.legacy.client import connect


ROOT = Path(__file__).resolve().parents[1]
HARNESS_RUN_ROOT = ROOT / "scratch" / "harness-runs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a harness task over the orchestrator WebSocket contract")
    parser.add_argument("--task-file", default="")
    parser.add_argument("--task-dir", default="")
    parser.add_argument("--output-dir", default="")
    return parser.parse_args()


async def _send_request(
    websocket: Any,
    method: str,
    *,
    task_id: str | None = None,
    node_id: str | None = None,
    session_id: str | None = None,
    params: dict[str, Any] | None = None,
) -> None:
    await websocket.send(
        json.dumps(
            {
                "type": "req",
                "id": f"{method}-{task_id or session_id or 'request'}",
                "method": method,
                "taskId": task_id,
                "nodeId": node_id,
                "sessionId": session_id,
                "params": params or {},
            },
            ensure_ascii=False,
        )
    )


async def _recv_matching_event(
    websocket: Any,
    sink: list[dict[str, Any]],
    expected_event: str,
    *,
    session_id: str | None = None,
    timeout_seconds: float,
) -> dict[str, Any]:
    while True:
        raw_message = await asyncio.wait_for(websocket.recv(), timeout=timeout_seconds)
        message = json.loads(raw_message)
        if message.get("type") != "event":
            continue
        sink.append(message)
        if message.get("event") != expected_event:
            continue
        if session_id is not None and message.get("sessionId") != session_id:
            continue
        return message


async def run_task(task: HarnessTaskSpec, *, output_dir: Path | None = None) -> tuple[HarnessResult, dict[str, Any]]:
    output_path = output_dir or (HARNESS_RUN_ROOT / f"{task.task_id}-{uuid4().hex[:8]}")
    output_path.mkdir(parents=True, exist_ok=True)

    headers = {"X-MetaAgent-Token": task.token.strip()} if task.token.strip() else None
    events: list[dict[str, Any]] = []
    async with connect(task.ws_url, extra_headers=headers) as websocket:
        await _send_request(
            websocket,
            "orchestrator.session.start",
            task_id=task.task_id,
            node_id=task.node_id,
            params={
                "runner": task.runner,
                "workspace": task.workspace,
                "task": task.task,
                "goal": task.goal,
            },
        )
        started_event = await _recv_matching_event(
            websocket,
            events,
            "orchestrator.session.started",
            timeout_seconds=task.timeout_seconds,
        )
        session_id = str(started_event.get("sessionId") or "")
        terminal_event = await _recv_matching_event(
            websocket,
            events,
            task.expectation.terminal_event,
            session_id=session_id,
            timeout_seconds=task.timeout_seconds,
        )

        snapshot_payload: dict[str, Any] | None = None
        if task.query_snapshot:
            await _send_request(websocket, "orchestrator.session.snapshot", session_id=session_id, params={})
            snapshot_event = await _recv_matching_event(
                websocket,
                events,
                "orchestrator.session.snapshot",
                session_id=session_id,
                timeout_seconds=task.timeout_seconds,
            )
            snapshot_payload = dict(snapshot_event.get("payload") or {})

        history_items: list[dict[str, Any]] = []
        if task.query_history:
            await _send_request(
                websocket,
                "orchestrator.session.history",
                session_id=session_id,
                params={"limit": task.history_limit},
            )
            history_event = await _recv_matching_event(
                websocket,
                events,
                "orchestrator.session.history",
                session_id=session_id,
                timeout_seconds=task.timeout_seconds,
            )
            history_items = list((history_event.get("payload") or {}).get("items") or [])

        trace_items: list[dict[str, Any]] = []
        if task.query_trace:
            await _send_request(
                websocket,
                "orchestrator.session.trace",
                session_id=session_id,
                params={"limit": task.trace_limit},
            )
            trace_event = await _recv_matching_event(
                websocket,
                events,
                "orchestrator.session.trace",
                session_id=session_id,
                timeout_seconds=task.timeout_seconds,
            )
            trace_items = list((trace_event.get("payload") or {}).get("items") or [])

        error_items: list[dict[str, Any]] = []
        if task.query_errors:
            await _send_request(
                websocket,
                "orchestrator.session.errors",
                session_id=session_id,
                params={"limit": task.errors_limit},
            )
            errors_event = await _recv_matching_event(
                websocket,
                events,
                "orchestrator.session.errors",
                session_id=session_id,
                timeout_seconds=task.timeout_seconds,
            )
            error_items = list((errors_event.get("payload") or {}).get("items") or [])

        artifact_payload: dict[str, Any] = {}
        if task.query_artifacts:
            await _send_request(
                websocket,
                "orchestrator.session.artifacts",
                session_id=session_id,
                params={"limit": task.artifacts_limit},
            )
            artifacts_event = await _recv_matching_event(
                websocket,
                events,
                "orchestrator.session.artifacts",
                session_id=session_id,
                timeout_seconds=task.timeout_seconds,
            )
            artifact_payload = dict(artifacts_event.get("payload") or {})

    result = HarnessResult(
        task={
            "taskId": task.task_id,
            "nodeId": task.node_id,
            "runner": task.runner,
            "workspace": task.workspace,
            "task": task.task,
            "goal": task.goal,
            "wsUrl": task.ws_url,
        },
        session_id=session_id,
        terminal_event=terminal_event,
        events=events,
        snapshot=dict(snapshot_payload.get("snapshot") or {}) if snapshot_payload else None,
        history=history_items,
        trace=trace_items,
        errors=error_items,
        artifacts=artifact_payload,
        output_dir=str(output_path),
    )
    evaluation = evaluate_harness_result(task, result).to_dict()
    (output_path / "result.json").write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (output_path / "evaluation.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    return result, evaluation


async def run_task_file(task_file: Path, *, output_dir: Path | None = None) -> tuple[HarnessResult, dict[str, Any]]:
    return await run_task(HarnessTaskSpec.load(task_file), output_dir=output_dir)


async def run_task_files(task_files: list[Path], *, output_dir: Path | None = None) -> HarnessBatchSummary:
    if not task_files:
        raise ValueError("No harness task files were found.")
    base_output_dir = output_dir or (HARNESS_RUN_ROOT / f"batch-{uuid4().hex[:8]}")
    base_output_dir.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []

    for task_file in task_files:
        task = HarnessTaskSpec.load(task_file)
        task_output_dir = base_output_dir / task.task_id
        result, evaluation = await run_task(task, output_dir=task_output_dir)
        runs.append(
            {
                "taskFile": str(task_file),
                "taskId": task.task_id,
                "ok": bool(evaluation.get("ok")),
                "outputDir": str(task_output_dir),
                "evaluation": evaluation,
                "sessionId": result.session_id,
            }
        )

    summary = HarnessBatchSummary(
        ok=all(bool(item["ok"]) for item in runs),
        task_count=len(runs),
        passed_count=sum(1 for item in runs if item["ok"]),
        failed_count=sum(1 for item in runs if not item["ok"]),
        runs=runs,
    )
    (base_output_dir / "summary.json").write_text(
        json.dumps(summary.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir) if args.output_dir else None
    if args.task_dir:
        task_files = sorted(Path(args.task_dir).glob("*.json"))
        summary = asyncio.run(run_task_files(task_files, output_dir=output_dir))
        print(json.dumps({"summary": summary.to_dict()}, ensure_ascii=False, indent=2))
        return
    if not args.task_file:
        raise SystemExit("Either --task-file or --task-dir is required.")
    result, evaluation = asyncio.run(run_task_file(Path(args.task_file), output_dir=output_dir))
    print(json.dumps({"result": result.to_dict(), "evaluation": evaluation}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
