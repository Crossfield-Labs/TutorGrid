from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any

from backend.knowledge.service import KnowledgeBaseService
from backend.knowledge.store import SQLiteKnowledgeStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark knowledge-base ingestion for local files.")
    parser.add_argument("paths", nargs="*", help="File paths to ingest.")
    parser.add_argument("--manifest", default="", help="Optional json file with `documents` list.")
    parser.add_argument("--db-path", default="scratch/ingest-benchmark/orchestrator.sqlite3")
    parser.add_argument("--kb-root", default="scratch/ingest-benchmark/knowledge_bases")
    parser.add_argument("--course-name", default="Ingest Benchmark")
    parser.add_argument("--course-description", default="local benchmark run")
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--output", default="", help="Optional output json path.")
    return parser.parse_args()


def _resolve_path(parent: Path, raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = (parent / candidate).resolve()
    return candidate


def _load_targets(*, args: argparse.Namespace) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for raw in args.paths:
        file_path = _resolve_path(Path.cwd(), raw)
        targets.append({"path": str(file_path), "name": file_path.name, "chunkSize": int(args.chunk_size)})
    manifest_path = str(args.manifest or "").strip()
    if not manifest_path:
        return targets
    manifest_file = Path(manifest_path).expanduser().resolve()
    if not manifest_file.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_file}")
    raw = json.loads(manifest_file.read_text(encoding="utf-8"))
    parent = manifest_file.parent
    if isinstance(raw, dict):
        document_entries = raw.get("documents", [])
    elif isinstance(raw, list):
        document_entries = raw
    else:
        raise ValueError("Manifest must be an object with `documents` or an array.")
    if not isinstance(document_entries, list):
        raise ValueError("Manifest `documents` must be an array.")
    for item in document_entries:
        if isinstance(item, str):
            file_path = _resolve_path(parent, item)
            targets.append({"path": str(file_path), "name": file_path.name, "chunkSize": int(args.chunk_size)})
            continue
        if not isinstance(item, dict):
            raise ValueError("Manifest document entries must be string or object.")
        raw_path = str(item.get("path") or "").strip()
        if not raw_path:
            raise ValueError("Each manifest document object must include `path`.")
        file_path = _resolve_path(parent, raw_path)
        targets.append(
            {
                "path": str(file_path),
                "name": str(item.get("name") or "").strip() or file_path.name,
                "chunkSize": int(item.get("chunkSize") or 0) or int(args.chunk_size),
            }
        )
    dedup: dict[str, dict[str, Any]] = {}
    for item in targets:
        dedup[str(item["path"])] = item
    return list(dedup.values())


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    targets = _load_targets(args=args)
    if not targets:
        raise ValueError("No input files found. Provide file paths or --manifest.")

    db_path = Path(args.db_path).expanduser().resolve()
    kb_root = Path(args.kb_root).expanduser().resolve()
    store = SQLiteKnowledgeStore(db_path)
    service = KnowledgeBaseService(store=store, root=kb_root)
    course = service.create_course(name=str(args.course_name).strip() or "Ingest Benchmark", description=str(args.course_description or "").strip())
    course_id = str(course["courseId"])

    records: list[dict[str, Any]] = []
    run_begin = time.perf_counter()
    for target in targets:
        file_path = str(target["path"])
        if not Path(file_path).exists():
            records.append(
                {
                    "filePath": file_path,
                    "fileName": str(target.get("name") or Path(file_path).name),
                    "status": "failed",
                    "chunkCount": 0,
                    "durationMs": 0.0,
                    "error": "file not found",
                }
            )
            continue
        begin = time.perf_counter()
        ingest_result = service.ingest_file(
            course_id=course_id,
            file_path=file_path,
            file_name=str(target.get("name") or ""),
            chunk_size=max(200, int(target.get("chunkSize") or args.chunk_size)),
        )
        elapsed_ms = (time.perf_counter() - begin) * 1000.0
        records.append(
            {
                "filePath": file_path,
                "fileName": str(target.get("name") or Path(file_path).name),
                "status": str(ingest_result.get("status") or ""),
                "chunkCount": int(ingest_result.get("chunkCount") or 0),
                "durationMs": elapsed_ms,
                "error": str(ingest_result.get("error") or ""),
            }
        )

    total_duration_ms = (time.perf_counter() - run_begin) * 1000.0
    success_count = sum(1 for item in records if item["status"] == "success")
    failed_count = len(records) - success_count
    total_chunks = sum(int(item["chunkCount"]) for item in records)
    total_seconds = max(0.001, total_duration_ms / 1000.0)

    return {
        "runAt": datetime.now(timezone.utc).isoformat(),
        "courseId": course_id,
        "dbPath": str(db_path),
        "kbRoot": str(kb_root),
        "summary": {
            "totalFiles": len(records),
            "successFiles": success_count,
            "failedFiles": failed_count,
            "totalChunks": total_chunks,
            "totalDurationMs": total_duration_ms,
            "avgFileDurationMs": total_duration_ms / float(max(1, len(records))),
            "filesPerMinute": (len(records) / total_seconds) * 60.0,
            "chunksPerSecond": total_chunks / total_seconds,
        },
        "records": records,
    }


def main() -> None:
    args = parse_args()
    output = run_benchmark(args)
    rendered = json.dumps(output, ensure_ascii=False, indent=2)
    print(rendered)
    output_path = str(args.output or "").strip()
    if output_path:
        target = Path(output_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")
        print(f"[saved] {target}")


if __name__ == "__main__":
    main()
