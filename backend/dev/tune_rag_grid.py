from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from backend.dev.compare_rag_profiles import load_profiles, temporary_env
from backend.dev.evaluate_rag import run_evaluation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RAG grid tuning over chunk sizes and profiles.")
    parser.add_argument("--dataset", required=True, help="Path to evaluation dataset json.")
    parser.add_argument("--profiles", default="", help="Optional profiles json path.")
    parser.add_argument("--chunk-sizes", default="600,900,1200", help="Comma-separated chunk sizes.")
    parser.add_argument("--db-path", default="scratch/eval-rag/grid/orchestrator.sqlite3")
    parser.add_argument("--kb-root", default="scratch/eval-rag/grid/knowledge_bases")
    parser.add_argument("--default-limit", type=int, default=8)
    parser.add_argument("--ks", default="1,3,5")
    parser.add_argument("--max-queries", type=int, default=0)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--output-json", default="scratch/eval-rag/grid/tune_report.json")
    parser.add_argument("--output-md", default="scratch/eval-rag/grid/tune_report.md")
    return parser.parse_args()


def parse_chunk_sizes(raw: str) -> list[int]:
    output: list[int] = []
    for part in str(raw or "").split(","):
        cleaned = part.strip()
        if not cleaned:
            continue
        try:
            output.append(max(200, int(cleaned)))
        except ValueError:
            continue
    unique = sorted(set(output))
    return unique or [900]


def build_eval_args(
    *,
    args: argparse.Namespace,
    chunk_size: int,
    reuse_course_id: str,
    skip_queries: bool,
) -> SimpleNamespace:
    return SimpleNamespace(
        dataset=args.dataset,
        db_path=args.db_path,
        kb_root=args.kb_root,
        course_name=f"RAG Grid chunk={chunk_size}",
        course_description="grid tuning run",
        chunk_size=chunk_size,
        default_limit=int(args.default_limit),
        ks=args.ks,
        max_queries=int(args.max_queries),
        reuse_course_id=reuse_course_id,
        output="",
        skip_queries=skip_queries,
    )


def variant_score(metrics: dict[str, Any]) -> float:
    recall = metrics.get("recallAtK", {})
    mrr = float(metrics.get("mrr", 0.0))
    r1 = float(recall.get("R@1", 0.0))
    r3 = float(recall.get("R@3", 0.0))
    r5 = float(recall.get("R@5", 0.0))
    latency_ms = float(metrics.get("meanLatencyMs", 0.0))
    return (100.0 * mrr) + (30.0 * r3) + (10.0 * r1) + (5.0 * r5) - (0.01 * latency_ms)


def rank_variants(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        variants,
        key=lambda item: (
            float(item.get("score", 0.0)),
            float(item.get("metrics", {}).get("mrr", 0.0)),
            float(item.get("metrics", {}).get("recallAtK", {}).get("R@3", 0.0)),
            -float(item.get("metrics", {}).get("meanLatencyMs", 0.0)),
        ),
        reverse=True,
    )


def render_markdown_table(variants: list[dict[str, Any]], *, top_n: int) -> str:
    head = [
        "| Rank | Chunk Size | Profile | Score | MRR | R@1 | R@3 | R@5 | Mean Latency (ms) |",
        "|---:|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for rank, item in enumerate(variants[: max(1, int(top_n))], start=1):
        metrics = item.get("metrics", {})
        recall = metrics.get("recallAtK", {})
        head.append(
            "| {rank} | {chunk} | {profile} | {score:.3f} | {mrr:.4f} | {r1:.4f} | {r3:.4f} | {r5:.4f} | {lat:.2f} |".format(
                rank=rank,
                chunk=int(item.get("chunkSize", 0)),
                profile=str(item.get("profile") or ""),
                score=float(item.get("score", 0.0)),
                mrr=float(metrics.get("mrr", 0.0)),
                r1=float(recall.get("R@1", 0.0)),
                r3=float(recall.get("R@3", 0.0)),
                r5=float(recall.get("R@5", 0.0)),
                lat=float(metrics.get("meanLatencyMs", 0.0)),
            )
        )
    return "\n".join(head)


async def run_grid_tuning(args: argparse.Namespace) -> dict[str, Any]:
    chunk_sizes = parse_chunk_sizes(args.chunk_sizes)
    profiles = load_profiles(args.profiles)
    variants: list[dict[str, Any]] = []
    ingest_runs: list[dict[str, Any]] = []

    for chunk_size in chunk_sizes:
        ingest_args = build_eval_args(args=args, chunk_size=chunk_size, reuse_course_id="", skip_queries=True)
        ingest_output = await run_evaluation(ingest_args)
        course_id = str(ingest_output.get("courseId") or "")
        if not course_id:
            raise RuntimeError(f"Failed to ingest dataset for chunk size {chunk_size}.")
        ingest_runs.append(
            {
                "chunkSize": chunk_size,
                "courseId": course_id,
                "ingest": ingest_output.get("ingest", {}),
            }
        )

        for profile in profiles:
            env_overrides = dict(profile.get("env") or {})
            eval_args = build_eval_args(args=args, chunk_size=chunk_size, reuse_course_id=course_id, skip_queries=False)
            with temporary_env(env_overrides):
                result = await run_evaluation(eval_args)
            metrics = result.get("metrics", {})
            score = variant_score(metrics if isinstance(metrics, dict) else {})
            variants.append(
                {
                    "chunkSize": chunk_size,
                    "profile": str(profile.get("name") or ""),
                    "description": str(profile.get("description") or ""),
                    "env": env_overrides,
                    "metrics": metrics,
                    "querySummary": result.get("queries", {}),
                    "score": score,
                }
            )

    ranked = rank_variants(variants)
    best = ranked[0] if ranked else None
    top_n = max(1, int(args.top_n))
    markdown = render_markdown_table(ranked, top_n=top_n)
    output: dict[str, Any] = {
        "runAt": datetime.now(timezone.utc).isoformat(),
        "datasetPath": str(Path(args.dataset).expanduser().resolve()),
        "chunkSizes": chunk_sizes,
        "profileCount": len(profiles),
        "ingestRuns": ingest_runs,
        "variants": ranked,
        "best": best,
        "topN": top_n,
        "tableMarkdown": markdown,
    }
    return output


def _save_output(path_text: str, content: str) -> Path:
    target = Path(path_text).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


async def main_async() -> None:
    args = parse_args()
    output = await run_grid_tuning(args)
    rendered_json = json.dumps(output, ensure_ascii=False, indent=2)
    print(rendered_json)
    print("\n" + str(output.get("tableMarkdown") or ""))
    if str(args.output_json or "").strip():
        saved = _save_output(args.output_json, rendered_json + "\n")
        print(f"[saved-json] {saved}")
    if str(args.output_md or "").strip():
        saved = _save_output(args.output_md, str(output.get("tableMarkdown") or "") + "\n")
        print(f"[saved-md] {saved}")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
