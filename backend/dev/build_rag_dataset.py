from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build RAG evaluation dataset json from docs + csv questions.")
    parser.add_argument("--course-name", required=True)
    parser.add_argument("--course-description", default="")
    parser.add_argument("--questions-csv", required=True, help="CSV with columns: id,question,expected_phrases,limit,...")
    parser.add_argument("--doc-paths", nargs="*", default=[], help="Explicit document paths.")
    parser.add_argument("--doc-manifest", default="", help="Optional json/line-delimited list for document paths.")
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--default-limit", type=int, default=8)
    parser.add_argument("--output", required=True, help="Output dataset json path.")
    parser.add_argument("--strict", action="store_true", help="Fail when files are missing or CSV rows are invalid.")
    return parser.parse_args()


def _resolve_path(parent: Path, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path.resolve()
    cwd_candidate = (Path.cwd() / path).resolve()
    parent_candidate = (parent / path).resolve()
    if cwd_candidate.exists() and not parent_candidate.exists():
        return cwd_candidate
    if parent_candidate.exists() and not cwd_candidate.exists():
        return parent_candidate
    if cwd_candidate.exists() and parent_candidate.exists():
        return cwd_candidate
    return parent_candidate


def _load_doc_manifest(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        return [line.strip() for line in text.splitlines() if line.strip()]
    if isinstance(raw, list):
        output: list[str] = []
        for item in raw:
            if isinstance(item, str):
                cleaned = item.strip()
                if cleaned:
                    output.append(cleaned)
            elif isinstance(item, dict):
                cleaned = str(item.get("path") or "").strip()
                if cleaned:
                    output.append(cleaned)
        return output
    if isinstance(raw, dict):
        documents = raw.get("documents")
        if isinstance(documents, list):
            output: list[str] = []
            for item in documents:
                if isinstance(item, str):
                    cleaned = item.strip()
                elif isinstance(item, dict):
                    cleaned = str(item.get("path") or "").strip()
                else:
                    cleaned = ""
                if cleaned:
                    output.append(cleaned)
            return output
    return []


def _split_expected_phrases(raw: str) -> list[str]:
    phrases: list[str] = []
    for part in str(raw or "").split("|"):
        cleaned = part.strip()
        if cleaned:
            phrases.append(cleaned)
    return phrases


def build_dataset(
    *,
    course_name: str,
    course_description: str,
    questions_csv: Path,
    doc_paths: list[str],
    doc_manifest: str,
    chunk_size: int,
    default_limit: int,
    strict: bool,
) -> tuple[dict[str, Any], list[str], list[str]]:
    parent = questions_csv.parent
    problems: list[str] = []
    warnings: list[str] = []

    normalized_docs: list[str] = []
    for item in doc_paths:
        cleaned = str(item or "").strip()
        if cleaned:
            normalized_docs.append(cleaned)

    manifest_path_text = str(doc_manifest or "").strip()
    if manifest_path_text:
        manifest_path = _resolve_path(parent, manifest_path_text)
        if not manifest_path.exists():
            problems.append(f"doc manifest not found: {manifest_path}")
        else:
            normalized_docs.extend(_load_doc_manifest(manifest_path))

    dedup_docs: dict[str, str] = {}
    documents: list[dict[str, Any]] = []
    for raw_path in normalized_docs:
        resolved = _resolve_path(parent, raw_path)
        dedup_docs[str(resolved)] = raw_path
    for resolved_text in sorted(dedup_docs.keys()):
        resolved = Path(resolved_text)
        if not resolved.exists():
            message = f"document file not found: {resolved}"
            if strict:
                problems.append(message)
            else:
                warnings.append(message)
                continue
        documents.append(
            {
                "path": str(resolved),
                "name": resolved.name,
                "chunkSize": max(200, int(chunk_size)),
            }
        )
    if strict and not documents:
        problems.append("no valid documents were resolved.")

    if not questions_csv.exists():
        problems.append(f"questions csv not found: {questions_csv}")
        return ({}, problems, warnings)

    queries: list[dict[str, Any]] = []
    with questions_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            problems.append("questions csv has no header row.")
            return ({}, problems, warnings)
        for index, row in enumerate(reader, start=2):
            question = str(row.get("question") or "").strip()
            if not question:
                message = f"csv row {index}: missing `question`."
                if strict:
                    problems.append(message)
                else:
                    warnings.append(message)
                continue
            raw_limit = str(row.get("limit") or "").strip()
            try:
                limit = max(1, int(raw_limit)) if raw_limit else max(1, int(default_limit))
            except ValueError:
                message = f"csv row {index}: invalid `limit` value `{raw_limit}`."
                if strict:
                    problems.append(message)
                    continue
                warnings.append(message)
                limit = max(1, int(default_limit))
            expected_phrases = _split_expected_phrases(str(row.get("expected_phrases") or row.get("expectedPhrases") or ""))
            if strict and not expected_phrases:
                problems.append(f"csv row {index}: strict mode requires `expected_phrases`.")
                continue
            query: dict[str, Any] = {
                "question": question,
                "expectedPhrases": expected_phrases,
                "limit": limit,
            }
            for key in ("id", "difficulty", "type", "notes"):
                value = str(row.get(key) or "").strip()
                if value:
                    query[key] = value
            queries.append(query)

    if strict and not queries:
        problems.append("no valid queries were parsed from csv.")

    dataset = {
        "courseName": course_name.strip() or "RAG Dataset",
        "courseDescription": course_description.strip(),
        "documents": documents,
        "queries": queries,
    }
    return dataset, problems, warnings


def main() -> None:
    args = parse_args()
    questions_csv = Path(args.questions_csv).expanduser().resolve()
    dataset, problems, warnings = build_dataset(
        course_name=args.course_name,
        course_description=args.course_description,
        questions_csv=questions_csv,
        doc_paths=[str(item) for item in args.doc_paths],
        doc_manifest=args.doc_manifest,
        chunk_size=max(200, int(args.chunk_size)),
        default_limit=max(1, int(args.default_limit)),
        strict=bool(args.strict),
    )
    payload = {"dataset": dataset, "problems": problems, "warnings": warnings}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if problems:
        raise SystemExit(2)
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[saved] {output_path}")


if __name__ == "__main__":
    main()
