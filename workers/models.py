from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class WorkerArtifact:
    path: str
    change_type: str
    size: int | None = None


@dataclass(slots=True)
class WorkerProgressEvent:
    phase: str
    message: str
    detail: str = ""
    raw_type: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkerResult:
    worker: str
    success: bool
    summary: str
    output: str
    artifacts: list[WorkerArtifact] = field(default_factory=list)
    raw_events: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""

    def to_tool_payload(self) -> str:
        lines = [
            f"Worker: {self.worker}",
            f"Success: {'yes' if self.success else 'no'}",
        ]
        if self.summary:
            lines.extend(["Summary:", self.summary.strip()])
        if self.artifacts:
            lines.append("Artifacts:")
            lines.extend(
                f"- {artifact.change_type}: {artifact.path}"
                + (f" ({artifact.size} bytes)" if artifact.size is not None else "")
                for artifact in self.artifacts[:12]
            )
            remaining = len(self.artifacts) - 12
            if remaining > 0:
                lines.append(f"- ... and {remaining} more")
        if self.error:
            lines.extend(["Error:", self.error.strip()])
        elif self.output:
            output = self.output.strip()
            lines.extend(["Output:", output[:6000]])
        return "\n".join(lines).strip()

    def to_record(
        self,
        *,
        include_raw_events: bool = True,
        output_limit: int | None = None,
    ) -> dict[str, Any]:
        output = self.output
        if output_limit is not None and len(output) > output_limit:
            output = output[:output_limit] + "\n...[truncated]"
        record = {
            "worker": self.worker,
            "success": self.success,
            "summary": self.summary,
            "output": output,
            "error": self.error,
            "artifacts": [
                {
                    "path": artifact.path,
                    "change_type": artifact.change_type,
                    "size": artifact.size,
                }
                for artifact in self.artifacts
            ],
        }
        if include_raw_events:
            record["raw_events"] = self.raw_events
        return record

    def to_json(self, *, include_raw_events: bool = False) -> str:
        return json.dumps(
            self.to_record(include_raw_events=include_raw_events, output_limit=2500 if not include_raw_events else None),
            ensure_ascii=False,
        )
