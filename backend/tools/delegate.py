from __future__ import annotations

from typing import Any

from backend.workers.models import WorkerControlRef, WorkerProgressEvent, WorkerResult
from backend.workers.selection import select_session_mode, select_worker, select_worker_profile


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
        preferred_worker=worker,
    )
    normalized_session_key = (session_key or "primary").strip() or "primary"

    if session is not None:
        session.context.setdefault("worker_sessions", dict(session.worker_sessions))
        session.set_latest_summary(f"Selected worker {selection.worker}: {selection.reason}")

    async def on_progress(event: WorkerProgressEvent) -> None:
        if session is None:
            return
        metadata = dict(event.metadata or {})
        selected_worker = str(metadata.get("selected_worker") or metadata.get("worker") or "").strip()
        session_mode_value = str(metadata.get("session_mode") or "").strip()
        worker_profile = str(metadata.get("worker_profile") or "").strip()
        task_id = str(metadata.get("task_id") or "").strip()

        if selected_worker:
            session.set_active_worker_runtime(
                worker=selected_worker,
                session_mode=session_mode_value or session.active_session_mode,
                task_id=task_id or session.active_worker_task_id,
                profile=worker_profile or session.active_worker_profile,
                can_interrupt=session.active_worker_can_interrupt,
            )
        elif session.active_worker and (session_mode_value or worker_profile or task_id):
            session.set_active_worker_runtime(
                worker=session.active_worker,
                session_mode=session_mode_value or session.active_session_mode,
                task_id=task_id or session.active_worker_task_id,
                profile=worker_profile or session.active_worker_profile,
                can_interrupt=session.active_worker_can_interrupt,
            )

        hook_event = str(metadata.get("hook_event") or "").strip()
        if hook_event:
            session.add_hook_event(
                name=hook_event,
                message=event.message,
                tool_name=str(metadata.get("tool_name") or "").strip(),
                status=str(metadata.get("hook_status") or "").strip(),
            )
        permission_summary = str(metadata.get("permission_summary") or "").strip()
        if permission_summary:
            session.set_permission_summary(permission_summary)
        session_info_summary = str(metadata.get("session_info_summary") or "").strip()
        if session_info_summary:
            session.set_session_info_summary(session_info_summary)
        mcp_status_summary = str(metadata.get("mcp_status_summary") or "").strip()
        if mcp_status_summary:
            session.set_mcp_status_summary(mcp_status_summary)
        if event.phase.startswith("worker_"):
            session.set_phase("delegating")
        session.set_latest_summary(event.message)

    async def on_control(worker_name: str, control: WorkerControlRef | None) -> None:
        if session is None:
            return
        if control is None:
            session.context.pop("_active_worker_control", None)
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
            worker=worker_name,
            session_mode=session.active_session_mode,
            task_id=control.task_id,
            profile=session.active_worker_profile,
            can_interrupt=control.can_interrupt,
        )

    async def on_result(result: WorkerResult) -> None:
        if session is None:
            return
        record = result.to_record()
        session.worker_runs.append(record)
        artifact_paths = [artifact.path for artifact in result.artifacts]
        if artifact_paths:
            session.artifacts = sorted(set([*session.artifacts, *artifact_paths]))
            artifact_summary = f"{len(artifact_paths)} artifact(s): " + ", ".join(artifact_paths[:3])
            remaining = len(artifact_paths) - 3
            if remaining > 0:
                artifact_summary += f", and {remaining} more"
            session.set_latest_artifact_summary(artifact_summary)
        if result.metadata:
            permission_summary = str(result.metadata.get("permission_summary") or "").strip()
            if permission_summary:
                session.set_permission_summary(permission_summary)
            session_info_summary = str(result.metadata.get("session_info_summary") or "").strip()
            if session_info_summary:
                session.set_session_info_summary(session_info_summary)
            mcp_status_summary = str(result.metadata.get("mcp_status_summary") or "").strip()
            if mcp_status_summary:
                session.set_mcp_status_summary(mcp_status_summary)
        session.context["worker_runs"] = list(session.worker_runs)
        session.context["worker_sessions"] = dict(session.worker_sessions)
        session.set_phase("verifying" if result.success else "planning")
        session.set_latest_summary(result.summary or (result.output[:240] if result.output else f"{result.worker} finished"))

    attempts = [selection.worker, *selection.fallback_order]
    previous_error = ""
    last_result: WorkerResult | None = None

    if session is not None:
        session.set_active_worker_runtime(
            worker=selection.worker,
            session_mode="new",
            task_id="",
            profile="",
            can_interrupt=False,
        )

    for index, candidate in enumerate(attempts):
        candidate_task = task
        if index > 0 and previous_error:
            candidate_task = (
                f"{task}\n\n"
                f"Previous backend '{attempts[index - 1]}' failed or was unsuitable with this error:\n"
                f"{previous_error}\n\n"
                "Please continue the original task and finish it."
            )
            if session is not None:
                session.set_latest_summary(f"Rerouting from {attempts[index - 1]} to {candidate}")

        if session is not None:
            await on_progress(
                WorkerProgressEvent(
                    phase="worker_selection",
                    message=f"Selected worker {candidate}: {selection.reason if index == 0 else 'Fallback reroute after a previous backend failure.'}",
                    raw_type="selection",
                    metadata={"selected_worker": candidate, "fallback_order": attempts[index + 1 :]},
                )
            )

        backend = worker_registry.get(candidate)
        session_lookup_key = f"{candidate}:{normalized_session_key}"
        existing_session = session.worker_sessions.get(session_lookup_key) if session is not None else None
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

        if session is not None:
            await on_progress(
                WorkerProgressEvent(
                    phase="worker_session_policy",
                    message=f"Using session mode {mode_selection.mode} for {candidate}: {mode_selection.reason}",
                    raw_type="session_mode",
                    metadata={
                        "worker": candidate,
                        "session_mode": mode_selection.mode,
                        "session_key": normalized_session_key,
                        "has_existing_session": bool(existing_session),
                        "worker_profile": profile_selection.profile,
                    },
                )
            )
            if candidate == "claude" and profile_selection.profile:
                await on_progress(
                    WorkerProgressEvent(
                        phase="worker_profile",
                        message=f"Using {candidate} profile {profile_selection.profile}: {profile_selection.reason}",
                        raw_type="worker_profile",
                        metadata={
                            "worker": candidate,
                            "worker_profile": profile_selection.profile,
                            "worker_profile_reason": profile_selection.reason,
                        },
                    )
                )

        try:
            run_kwargs: dict[str, Any] = {
                "task": candidate_task,
                "workspace": workspace,
                "on_progress": on_progress if session is not None else None,
            }
            if candidate in {"codex", "claude"}:
                run_kwargs.update(
                    {
                        "session_id": str(existing_session.get("session_id") or "") if existing_session else "",
                        "session_mode": mode_selection.mode,
                        "session_key": normalized_session_key,
                    }
                )
            if candidate == "claude":
                run_kwargs.update(
                    {
                        "profile": profile_selection.profile,
                        "on_control": (lambda control, current=candidate: on_control(current, control)),
                    }
                )
            result = await backend.run(**run_kwargs)
        except Exception as error:
            result = WorkerResult(
                worker=candidate,
                success=False,
                summary=f"{candidate} failed before producing a result.",
                output="",
                error=f"{error.__class__.__name__}: {error}",
            )

        await on_result(result)
        last_result = result
        if result.session is not None and session is not None:
            session.worker_sessions[session_lookup_key] = {
                "worker": result.session.worker,
                "session_id": result.session.session_id,
                "session_key": result.session.session_key,
                "mode": result.session.mode,
                "continued_from": result.session.continued_from,
            }
            session.context["worker_sessions"] = dict(session.worker_sessions)

        await on_control(candidate, None)

        if result.success:
            return result.to_json()

        previous_error = result.error or result.summary or f"{candidate} failed."

    if last_result is None:
        raise RuntimeError("No worker attempts were executed.")
    return last_result.to_json()


