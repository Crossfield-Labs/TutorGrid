from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class HarnessExpectation:
    required_events: list[str] = field(default_factory=list)
    terminal_event: str = "orchestrator.session.completed"
    terminal_status: str = "COMPLETED"
    require_message_stream: bool = False
    require_frame_metadata: bool = True
    min_history_items: int = 0
    min_trace_items: int = 0
    min_error_items: int = 0
    min_artifact_items: int = 0
    required_snapshot_fields: list[str] = field(default_factory=list)
    required_history_kinds: list[str] = field(default_factory=list)
    required_artifact_events: list[str] = field(default_factory=list)


@dataclass(slots=True)
class HarnessTaskSpec:
    task_id: str
    node_id: str
    runner: str
    workspace: str
    task: str
    goal: str = ""
    ws_url: str = "ws://127.0.0.1:3210/ws/orchestrator"
    token: str = ""
    timeout_seconds: float = 30.0
    query_snapshot: bool = True
    query_history: bool = True
    query_trace: bool = False
    query_errors: bool = False
    query_artifacts: bool = False
    history_limit: int = 50
    trace_limit: int = 50
    errors_limit: int = 50
    artifacts_limit: int = 50
    expectation: HarnessExpectation = field(default_factory=HarnessExpectation)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HarnessTaskSpec":
        expectation_payload = payload.get("expectation") or {}
        return cls(
            task_id=str(payload.get("taskId") or "harness-task"),
            node_id=str(payload.get("nodeId") or "harness-node"),
            runner=str(payload.get("runner") or "orchestrator"),
            workspace=str(payload.get("workspace") or "."),
            task=str(payload.get("task") or ""),
            goal=str(payload.get("goal") or ""),
            ws_url=str(payload.get("wsUrl") or "ws://127.0.0.1:3210/ws/orchestrator"),
            token=str(payload.get("token") or ""),
            timeout_seconds=float(payload.get("timeoutSeconds") or 30.0),
            query_snapshot=bool(payload.get("querySnapshot", True)),
            query_history=bool(payload.get("queryHistory", True)),
            query_trace=bool(payload.get("queryTrace", False)),
            query_errors=bool(payload.get("queryErrors", False)),
            query_artifacts=bool(payload.get("queryArtifacts", False)),
            history_limit=max(1, int(payload.get("historyLimit") or 50)),
            trace_limit=max(1, int(payload.get("traceLimit") or 50)),
            errors_limit=max(1, int(payload.get("errorsLimit") or 50)),
            artifacts_limit=max(1, int(payload.get("artifactsLimit") or 50)),
            expectation=HarnessExpectation(
                required_events=[str(item) for item in list(expectation_payload.get("requiredEvents") or [])],
                terminal_event=str(expectation_payload.get("terminalEvent") or "orchestrator.session.completed"),
                terminal_status=str(expectation_payload.get("terminalStatus") or "COMPLETED"),
                require_message_stream=bool(expectation_payload.get("requireMessageStream", False)),
                require_frame_metadata=bool(expectation_payload.get("requireFrameMetadata", True)),
                min_history_items=max(0, int(expectation_payload.get("minHistoryItems") or 0)),
                min_trace_items=max(0, int(expectation_payload.get("minTraceItems") or 0)),
                min_error_items=max(0, int(expectation_payload.get("minErrorItems") or 0)),
                min_artifact_items=max(0, int(expectation_payload.get("minArtifactItems") or 0)),
                required_snapshot_fields=[
                    str(item) for item in list(expectation_payload.get("requiredSnapshotFields") or [])
                ],
                required_history_kinds=[str(item) for item in list(expectation_payload.get("requiredHistoryKinds") or [])],
                required_artifact_events=[
                    str(item) for item in list(expectation_payload.get("requiredArtifactEvents") or [])
                ],
            ),
        )

    @classmethod
    def load(cls, path: Path) -> "HarnessTaskSpec":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


@dataclass(slots=True)
class HarnessResult:
    task: dict[str, Any]
    session_id: str
    terminal_event: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)
    snapshot: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    output_dir: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HarnessEvaluation:
    ok: bool
    checks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HarnessBatchSummary:
    ok: bool
    task_count: int
    passed_count: int
    failed_count: int
    runs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
