from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any

from backend.knowledge.service import KnowledgeBaseService
from backend.knowledge.store import SQLiteKnowledgeStore
from backend.rag import RagEvalCase, RagEvalResult, RagService, aggregate_rag_metrics, find_first_relevant_rank


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run offline RAG evaluation and output metrics.")
    parser.add_argument("--dataset", required=True, help="Path to evaluation dataset json.")
    parser.add_argument("--db-path", default="scratch/eval-rag/orchestrator.sqlite3")
    parser.add_argument("--kb-root", default="scratch/eval-rag/knowledge_bases")
    parser.add_argument("--course-name", default="")
    parser.add_argument("--course-description", default="")
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--default-limit", type=int, default=8)
    parser.add_argument("--ks", default="1,3,5", help="Comma-separated K values, e.g. 1,3,5,10")
    parser.add_argument("--max-queries", type=int, default=0, help="0 means no limit.")
    parser.add_argument("--reuse-course-id", default="", help="Skip ingestion and evaluate an existing course id.")
    parser.add_argument("--output", default="", help="Optional output json path.")
    return parser.parse_args()


def _parse_ks(raw: str) -> list[int]:
    values: list[int] = []
    for part in str(raw or "").split(","):
        cleaned = part.strip()
        if not cleaned:
            continue
        try:
            values.append(max(1, int(cleaned)))
        except ValueError:
            continue
    return sorted(set(values)) or [1, 3, 5]


def _load_dataset(dataset_path: Path, *, default_limit: int) -> tuple[str, str, list[dict[str, Any]], list[RagEvalCase]]:
    raw = json.loads(dataset_path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError("Dataset json root must be an object.")
    course_name = str(raw.get("courseName") or "").strip() or "RAG Evaluation Course"
    course_description = str(raw.get("courseDescription") or "").strip()
    parent = dataset_path.parent

    document_entries = raw.get("documents")
    if document_entries is None:
        document_entries = []
    if not isinstance(document_entries, list):
        raise ValueError("Dataset field `documents` must be an array.")
    documents: list[dict[str, Any]] = []
    for item in document_entries:
        if isinstance(item, str):
            file_path = _resolve_path(parent, item)
            documents.append({"path": str(file_path), "name": file_path.name})
            continue
        if not isinstance(item, dict):
            raise ValueError("Document entries must be string or object.")
        raw_path = str(item.get("path") or "").strip()
        if not raw_path:
            raise ValueError("Each document object must include a non-empty `path`.")
        file_path = _resolve_path(parent, raw_path)
        documents.append(
            {
                "path": str(file_path),
                "name": str(item.get("name") or "").strip() or file_path.name,
                "chunkSize": int(item.get("chunkSize") or 0),
            }
        )

    query_entries = raw.get("queries")
    if not isinstance(query_entries, list):
        raise ValueError("Dataset field `queries` must be an array.")
    cases: list[RagEvalCase] = []
    for item in query_entries:
        if not isinstance(item, dict):
            raise ValueError("Each query entry must be an object.")
        question = str(item.get("question") or "").strip()
        if not question:
            raise ValueError("Each query entry must include non-empty `question`.")
        expected = item.get("expectedPhrases")
        if expected is None:
            expected = item.get("relevantSnippets")
        phrases = _to_string_list(expected)
        limit = int(item.get("limit") or default_limit)
        metadata = {key: value for key, value in item.items() if key not in {"question", "expectedPhrases", "relevantSnippets", "limit"}}
        cases.append(
            RagEvalCase(
                question=question,
                expected_phrases=phrases,
                limit=max(1, limit),
                metadata=metadata,
            )
        )
    return course_name, course_description, documents, cases


def _resolve_path(parent: Path, raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = (parent / candidate).resolve()
    return candidate


def _to_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        output: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if text:
                output.append(text)
        return output
    return []


async def run_evaluation(args: argparse.Namespace) -> dict[str, Any]:
    dataset_path = Path(args.dataset).expanduser().resolve()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file does not exist: {dataset_path}")
    course_name, course_description, documents, cases = _load_dataset(dataset_path, default_limit=max(1, int(args.default_limit)))
    if args.max_queries and int(args.max_queries) > 0:
        cases = cases[: int(args.max_queries)]
    skip_queries = bool(getattr(args, "skip_queries", False))

    db_path = Path(args.db_path).expanduser().resolve()
    kb_root = Path(args.kb_root).expanduser().resolve()
    store = SQLiteKnowledgeStore(db_path)
    knowledge_service = KnowledgeBaseService(store=store, root=kb_root)
    rag_service = RagService(knowledge_service=knowledge_service)
    ks = _parse_ks(args.ks)

    ingest_records: list[dict[str, Any]] = []
    course_id = str(args.reuse_course_id or "").strip()
    if not course_id:
        course = knowledge_service.create_course(
            name=args.course_name.strip() or course_name,
            description=args.course_description.strip() or course_description,
        )
        course_id = str(course["courseId"])
        for item in documents:
            file_path = str(item["path"])
            display_name = str(item.get("name") or "").strip()
            chunk_size = int(item.get("chunkSize") or 0) or max(200, int(args.chunk_size))
            begin = time.perf_counter()
            ingest_result = knowledge_service.ingest_file(
                course_id=course_id,
                file_path=file_path,
                file_name=display_name,
                chunk_size=chunk_size,
            )
            elapsed_ms = (time.perf_counter() - begin) * 1000.0
            ingest_records.append(
                {
                    "filePath": file_path,
                    "fileName": display_name or Path(file_path).name,
                    "status": ingest_result.get("status"),
                    "chunkCount": int(ingest_result.get("chunkCount") or 0),
                    "durationMs": elapsed_ms,
                    "error": str(ingest_result.get("error") or ""),
                }
            )
        success_count = sum(1 for item in ingest_records if str(item.get("status")) == "success")
        if documents and success_count <= 0:
            raise RuntimeError("All ingestion tasks failed. Stop evaluation.")

    query_results: list[RagEvalResult] = []
    failed_queries: list[dict[str, Any]] = []
    if not skip_queries:
        for case in cases:
            begin = time.perf_counter()
            response = await rag_service.query(course_id=course_id, question=case.question, limit=case.limit)
            elapsed_ms = (time.perf_counter() - begin) * 1000.0
            items = response.get("items")
            safe_items = items if isinstance(items, list) else []
            rank = find_first_relevant_rank(safe_items, case.expected_phrases)
            query_results.append(
                RagEvalResult(
                    question=case.question,
                    expected_phrases=list(case.expected_phrases),
                    first_relevant_rank=rank,
                    retrieved_count=len(safe_items),
                    latency_ms=elapsed_ms,
                    metadata=dict(case.metadata),
                )
            )
            if case.expected_phrases and rank is None:
                failed_queries.append(
                    {
                        "question": case.question,
                        "expectedPhrases": case.expected_phrases,
                        "topContents": [str(item.get("content") or "")[:180] for item in safe_items[:3]],
                    }
                )

    metric_results = [item for item in query_results if item.expected_phrases]
    metrics = aggregate_rag_metrics(metric_results, ks=ks)

    ingest_success = sum(1 for item in ingest_records if str(item.get("status")) == "success")
    ingest_failed = sum(1 for item in ingest_records if str(item.get("status")) != "success")
    total_ingest_duration = sum(float(item.get("durationMs") or 0.0) for item in ingest_records)
    output = {
        "runAt": datetime.now(timezone.utc).isoformat(),
        "datasetPath": str(dataset_path),
        "courseId": course_id,
        "ks": ks,
        "ingest": {
            "totalFiles": len(ingest_records),
            "successFiles": ingest_success,
            "failedFiles": ingest_failed,
            "totalDurationMs": total_ingest_duration,
            "records": ingest_records,
        },
        "queries": {
            "totalQueries": len(query_results),
            "evaluatedQueries": len(metric_results),
            "skippedNoGroundTruth": len(query_results) - len(metric_results),
            "results": [
                {
                    "question": item.question,
                    "firstRelevantRank": item.first_relevant_rank,
                    "retrievedCount": item.retrieved_count,
                    "latencyMs": item.latency_ms,
                    "expectedPhrases": item.expected_phrases,
                    "metadata": item.metadata,
                }
                for item in query_results
            ],
            "failedSamples": failed_queries[:10],
        },
        "metrics": metrics,
    }
    return output


async def main_async() -> None:
    args = parse_args()
    output = await run_evaluation(args)
    rendered = json.dumps(output, ensure_ascii=False, indent=2)
    print(rendered)
    output_path = str(args.output or "").strip()
    if output_path:
        target = Path(output_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")
        print(f"[saved] {target}")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
