from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from backend.dev.compare_rag_profiles import run_compare
from backend.dev.summarize_rag_reports import build_recommendation, render_markdown
from backend.dev.tune_rag_grid import run_grid_tuning
from backend.dev.validate_rag_dataset import validate_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full RAG evaluation workflow in one command.")
    parser.add_argument("--dataset", required=True, help="Path to evaluation dataset json.")
    parser.add_argument("--profiles", default="", help="Optional profiles json path.")
    parser.add_argument("--chunk-sizes", default="600,900,1200")
    parser.add_argument("--default-limit", type=int, default=8)
    parser.add_argument("--ks", default="1,3,5")
    parser.add_argument("--max-queries", type=int, default=0)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--chunk-size-compare", type=int, default=900)
    parser.add_argument("--strict-validate", action="store_true")
    parser.add_argument("--run-root", default="scratch/eval-rag/workflow")
    parser.add_argument("--run-name", default="", help="Optional run folder name.")
    return parser.parse_args()


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _save_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_compare_args(args: argparse.Namespace, *, run_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        dataset=str(Path(args.dataset).expanduser().resolve()),
        profiles=str(args.profiles or ""),
        db_path=str(run_dir / "compare.sqlite3"),
        kb_root=str(run_dir / "compare_kb"),
        chunk_size=int(args.chunk_size_compare),
        default_limit=int(args.default_limit),
        ks=str(args.ks),
        max_queries=int(args.max_queries),
        output_json="",
        output_md="",
    )


def _build_grid_args(args: argparse.Namespace, *, run_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        dataset=str(Path(args.dataset).expanduser().resolve()),
        profiles=str(args.profiles or ""),
        chunk_sizes=str(args.chunk_sizes),
        db_path=str(run_dir / "grid.sqlite3"),
        kb_root=str(run_dir / "grid_kb"),
        default_limit=int(args.default_limit),
        ks=str(args.ks),
        max_queries=int(args.max_queries),
        top_n=int(args.top_n),
        output_json="",
        output_md="",
    )


async def run_workflow(args: argparse.Namespace) -> dict[str, Any]:
    dataset_path = Path(args.dataset).expanduser().resolve()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file does not exist: {dataset_path}")
    validation = validate_dataset(dataset_path, strict=bool(args.strict_validate))
    if not validation.get("ok"):
        raise RuntimeError("Dataset validation failed. Fix problems before running workflow.")

    run_root = Path(args.run_root).expanduser().resolve()
    run_name = str(args.run_name or "").strip() or _timestamp_slug()
    run_dir = run_root / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    compare_output = await run_compare(_build_compare_args(args, run_dir=run_dir))
    compare_json = run_dir / "profile_compare.json"
    compare_md = run_dir / "profile_compare.md"
    _save_json(compare_json, compare_output)
    _save_text(compare_md, str(compare_output.get("tableMarkdown") or "") + "\n")

    grid_output = await run_grid_tuning(_build_grid_args(args, run_dir=run_dir))
    grid_json = run_dir / "tune_report.json"
    grid_md = run_dir / "tune_report.md"
    _save_json(grid_json, grid_output)
    _save_text(grid_md, str(grid_output.get("tableMarkdown") or "") + "\n")

    recommendation = build_recommendation(profile_report=compare_output, grid_report=grid_output)
    recommendation_md_text = render_markdown(recommendation)
    recommendation_json = run_dir / "recommendation.json"
    recommendation_md = run_dir / "recommendation.md"
    _save_json(recommendation_json, recommendation)
    _save_text(recommendation_md, recommendation_md_text)

    manifest = {
        "runAt": datetime.now(timezone.utc).isoformat(),
        "runDir": str(run_dir),
        "datasetPath": str(dataset_path),
        "validation": validation,
        "artifacts": {
            "profileCompareJson": str(compare_json),
            "profileCompareMd": str(compare_md),
            "gridReportJson": str(grid_json),
            "gridReportMd": str(grid_md),
            "recommendationJson": str(recommendation_json),
            "recommendationMd": str(recommendation_md),
        },
        "recommended": recommendation.get("recommended", {}),
    }
    manifest_path = run_dir / "run_manifest.json"
    _save_json(manifest_path, manifest)
    manifest["manifestPath"] = str(manifest_path)
    return manifest


async def main_async() -> None:
    args = parse_args()
    output = await run_workflow(args)
    print(json.dumps(output, ensure_ascii=False, indent=2))


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
