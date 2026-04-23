from __future__ import annotations

from typing import Any

from harness.models import HarnessEvaluation, HarnessResult, HarnessTaskSpec


def evaluate_harness_result(task: HarnessTaskSpec, result: HarnessResult) -> HarnessEvaluation:
    event_names = [str(item.get("event") or "") for item in result.events]
    snapshot = result.snapshot or {}
    history_kinds = [str(item.get("kind") or "") for item in result.history]
    terminal_event_name = str(result.terminal_event.get("event") or "")
    terminal_index = next(
        (index for index, item in enumerate(result.events) if str(item.get("event") or "") == terminal_event_name),
        len(result.events) - 1,
    )
    realtime_events = result.events[: terminal_index + 1]
    checks: list[dict[str, Any]] = []

    for event_name in task.expectation.required_events:
        checks.append(
            {
                "name": f"event:{event_name}",
                "ok": event_name in event_names,
                "detail": f"found={event_name in event_names}",
            }
        )

    checks.append(
        {
            "name": "terminal_event",
            "ok": str(result.terminal_event.get("event") or "") == task.expectation.terminal_event,
            "detail": str(result.terminal_event.get("event") or ""),
        }
    )
    checks.append(
        {
            "name": "terminal_status",
            "ok": str(snapshot.get("status") or "") == task.expectation.terminal_status,
            "detail": str(snapshot.get("status") or ""),
        }
    )
    checks.append(
        {
            "name": "history_items",
            "ok": len(result.history) >= task.expectation.min_history_items,
            "detail": len(result.history),
        }
    )
    checks.append(
        {
            "name": "trace_items",
            "ok": len(result.trace) >= task.expectation.min_trace_items,
            "detail": len(result.trace),
        }
    )
    checks.append(
        {
            "name": "error_items",
            "ok": len(result.errors) >= task.expectation.min_error_items,
            "detail": len(result.errors),
        }
    )
    checks.append(
        {
            "name": "artifact_items",
            "ok": len(list(result.artifacts.get("items") or [])) >= task.expectation.min_artifact_items,
            "detail": len(list(result.artifacts.get("items") or [])),
        }
    )

    for field_name in task.expectation.required_snapshot_fields:
        checks.append(
            {
                "name": f"snapshot:{field_name}",
                "ok": field_name in snapshot,
                "detail": f"present={field_name in snapshot}",
            }
        )

    for kind in task.expectation.required_history_kinds:
        checks.append(
            {
                "name": f"history_kind:{kind}",
                "ok": kind in history_kinds,
                "detail": f"found={kind in history_kinds}",
            }
        )

    for event_name in task.expectation.required_artifact_events:
        checks.append(
            {
                "name": f"artifact_event:{event_name}",
                "ok": event_name in event_names,
                "detail": f"found={event_name in event_names}",
            }
        )

    if task.expectation.require_message_stream:
        message_events = {
            "orchestrator.session.message.started",
            "orchestrator.session.message.delta",
            "orchestrator.session.message.completed",
        }
        checks.append(
            {
                "name": "message_stream",
                "ok": message_events.issubset(set(event_names)),
                "detail": [name for name in event_names if name.startswith("orchestrator.session.message.")],
            }
        )

    if task.expectation.require_frame_metadata:
        metadata_ok = all(
            bool(item.get("timestamp")) and isinstance(item.get("seq"), int)
            for item in realtime_events
        )
        checks.append(
            {
                "name": "frame_metadata",
                "ok": metadata_ok,
                "detail": [
                    {
                        "event": item.get("event"),
                        "seq": item.get("seq"),
                        "timestamp": item.get("timestamp"),
                    }
                    for item in realtime_events[:10]
                ],
            }
        )

    return HarnessEvaluation(ok=all(bool(item["ok"]) for item in checks), checks=checks)
