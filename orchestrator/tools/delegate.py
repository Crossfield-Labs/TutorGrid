from __future__ import annotations

from typing import Any

from orchestrator.workers.models import WorkerControlRef, WorkerProgressEvent, WorkerResult
from orchestrator.workers.selection import select_session_mode, select_worker, select_worker_profile


async def delegate_task(
    *,
    task: str,
    worker: str,
    session_mode: str,
    session_key: str,
    profile: str,
    workspace: str,
    worker_registry: Any,
    session: Any | None = None,
) -> str:
    selection = select_worker(
        task=task,
        available_workers=worker_registry.list_names(),
        preferred_worker=worker or None,
    )
    normalized_session_key = (session_key or "primary").strip() or "primary"
    attempts = [selection.worker, *selection.fallback_order]
    previous_error = ""
    last_result: WorkerResult | None = None

    async def _on_progress(event: WorkerProgressEvent) -> None:
        if session is None:
            return
        metadata = dict(event.metadata or {})
        active_worker = str(metadata.get("selected_worker") or metadata.get("worker") or session.active_worker or "")
        if active_worker:
            session.set_active_worker_runtime(
                worker=active_worker,
                session_mode=str(metadata.get("session_mode") or session.active_session_mode or ""),
                task_id=str(metadata.get("task_id") or session.active_worker_task_id or ""),
                profile=str(metadata.get("worker_profile") or session.active_worker_profile or ""),
                can_interrupt=bool(getattr(session.context.get("_active_worker_control"), "can_interrupt", False)),
            )
        if metadata.get("permission_summary"):
            session.set_permission_summary(str(metadata.get("permission_summary") or ""))
        if metadata.get("session_info_summary"):
            session.set_session_info_summary(str(metadata.get("session_info_summary") or ""))
        if metadata.get("mcp_status_summary"):
            session.set_mcp_status_summary(str(metadata.get("mcp_status_summary") or ""))
        if metadata.get("hook_event"):
            session.add_hook_event(
                name=str(metadata.get("hook_event") or ""),
                message=event.message,
                tool_name=str(metadata.get("tool_name") or ""),
                status=str(metadata.get("hook_status") or ""),
            )
        session.set_latest_summary(event.message)

    async def _on_control(control: WorkerControlRef | None) -> None:
        if session is None:
            return
        if control is None:
            session.context.pop("_active_worker_control", None)
            if session.active_worker:
                session.set_active_worker_runtime(
                    worker=session.active_worker,
                    session_mode=session.active_session_mode,
                    task_id=session.active_worker_task_id,
                    profile=session.active_worker_profile,
                    can_interrupt=False,
                )
            return
        session.context["_active_worker_control"] = control
        session.set_active_worker_runtime(
            worker=control.worker,
            session_mode=session.active_session_mode,
            task_id=control.task_id,
            profile=session.active_worker_profile,
            can_interrupt=control.can_interrupt,
        )

    for index, candidate in enumerate(attempts):
        candidate_task = task
        if index > 0 and previous_error:
            candidate_task = (
                f"{task}\n\nPrevious backend '{attempts[index - 1]}' failed or was unsuitable with this error:\n"
                f"{previous_error}\n\nPlease continue the original task and finish it."
            )

        backend = worker_registry.get(candidate)
        existing_session = {}
        if session is not None:
            existing_session = dict(session.worker_sessions.get(f"{candidate}:{normalized_session_key}") or {})

        mode_selection = select_session_mode(
            worker=candidate,
            task=candidate_task,
            requested_mode=session_mode if index == 0 else "new",
            has_existing_session=bool(existing_session),
        )
        profile_selection = select_worker_profile(
            worker=candidate,
            task=candidate_task,
            requested_profile=profile if index == 0 else None,
        )
        result = await backend.run(
            candidate_task,
            workspace,
            on_progress=_on_progress,
            session_id=str(existing_session.get("session_id") or ""),
            session_mode=mode_selection.mode,
            session_key=normalized_session_key,
            profile=profile_selection.profile,
            on_control=_on_control,
        )
        last_result = result
        if session is not None:
            session.set_active_worker_runtime(
                worker=candidate,
                session_mode=mode_selection.mode,
                task_id=str(result.metadata.get("task_id") or session.active_worker_task_id or ""),
                profile=profile_selection.profile,
                can_interrupt=False,
            )
            if result.session is not None:
                session.worker_sessions[f"{candidate}:{normalized_session_key}"] = {
                    "worker": result.session.worker,
                    "session_id": result.session.session_id,
                    "session_key": result.session.session_key,
                    "mode": result.session.mode,
                    "continued_from": result.session.continued_from,
                }
            if result.artifacts:
                artifact_paths = [artifact.path for artifact in result.artifacts]
                session.artifacts = sorted(set([*session.artifacts, *artifact_paths]))
                artifact_summary = f"{len(artifact_paths)} artifact(s): " + ", ".join(artifact_paths[:3])
                if len(artifact_paths) > 3:
                    artifact_summary += f", and {len(artifact_paths) - 3} more"
                session.set_latest_artifact_summary(artifact_summary)
            session.worker_runs.append(
                {
                    "worker": candidate,
                    "success": result.success,
                    "summary": f"{selection.reason} {result.summary}".strip(),
                    "output": result.output,
                    "error": result.error,
                    "artifacts": [
                        {"path": artifact.path, "change_type": artifact.change_type, "size": artifact.size}
                        for artifact in result.artifacts
                    ],
                    "metadata": dict(result.metadata),
                    "session": (
                        {
                            "worker": result.session.worker,
                            "session_id": result.session.session_id,
                            "session_key": result.session.session_key,
                            "mode": result.session.mode,
                            "continued_from": result.session.continued_from,
                        }
                        if result.session is not None
                        else None
                    ),
                }
            )
        if result.success:
            await _on_control(None)
            return result.to_json(include_raw_events=False)
        previous_error = result.error or result.summary or f"{candidate} failed."
        await _on_control(None)

    if last_result is None:
        raise RuntimeError("No worker attempts were executed.")
    return last_result.to_json(include_raw_events=False)
