from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate RAG dataset format and local file existence.")
    parser.add_argument("--dataset", required=True, help="Path to dataset json.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict checks: require expectedPhrases and minimum query/doc counts.",
    )
    return parser.parse_args()


def _resolve_path(parent: Path, raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = (parent / candidate).resolve()
    return candidate


def validate_dataset(path: Path, *, strict: bool) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Dataset root must be a json object.")
    parent = path.parent
    problems: list[str] = []
    warnings: list[str] = []

    documents = raw.get("documents")
    if not isinstance(documents, list) or not documents:
        problems.append("`documents` must be a non-empty array.")
        documents = []
    queries = raw.get("queries")
    if not isinstance(queries, list) or not queries:
        problems.append("`queries` must be a non-empty array.")
        queries = []

    for idx, item in enumerate(documents, start=1):
        if isinstance(item, str):
            file_path = _resolve_path(parent, item)
            if not file_path.exists():
                problems.append(f"documents[{idx}] file not found: {file_path}")
            continue
        if not isinstance(item, dict):
            problems.append(f"documents[{idx}] must be string or object.")
            continue
        raw_path = str(item.get("path") or "").strip()
        if not raw_path:
            problems.append(f"documents[{idx}] missing `path`.")
            continue
        file_path = _resolve_path(parent, raw_path)
        if not file_path.exists():
            problems.append(f"documents[{idx}] file not found: {file_path}")
        chunk_size = int(item.get("chunkSize") or 0)
        if chunk_size and chunk_size < 200:
            warnings.append(f"documents[{idx}] chunkSize={chunk_size} is very small.")

    for idx, item in enumerate(queries, start=1):
        if not isinstance(item, dict):
            problems.append(f"queries[{idx}] must be object.")
            continue
        question = str(item.get("question") or "").strip()
        if not question:
            problems.append(f"queries[{idx}] missing non-empty `question`.")
        expected = item.get("expectedPhrases")
        if strict:
            if not isinstance(expected, list) or not [str(x).strip() for x in expected if str(x).strip()]:
                problems.append(f"queries[{idx}] strict mode requires non-empty `expectedPhrases`.")
        else:
            if expected is None:
                warnings.append(f"queries[{idx}] has no `expectedPhrases`; it will be skipped in metrics.")
        limit = int(item.get("limit") or 0)
        if limit and limit < 1:
            problems.append(f"queries[{idx}] invalid `limit`: {limit}")

    if strict:
        if len(documents) < 5:
            warnings.append("Strict mode: less than 5 documents may produce unstable benchmark signal.")
        if len(queries) < 20:
            warnings.append("Strict mode: less than 20 queries may produce unstable benchmark signal.")

    return {
        "datasetPath": str(path),
        "documentCount": len(documents),
        "queryCount": len(queries),
        "problems": problems,
        "warnings": warnings,
        "ok": len(problems) == 0,
    }


def main() -> None:
    args = parse_args()
    dataset_path = Path(args.dataset).expanduser().resolve()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file does not exist: {dataset_path}")
    result = validate_dataset(dataset_path, strict=bool(args.strict))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if not result["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
