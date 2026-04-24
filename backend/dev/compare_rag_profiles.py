from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

from backend.dev.evaluate_rag import run_evaluation


DEFAULT_PROFILES: list[dict[str, Any]] = [
    {
        "name": "baseline",
        "description": "Disable multi-query, HyDE and rerank",
        "env": {
            "ORCHESTRATOR_RAG_MULTI_QUERY": "0",
            "ORCHESTRATOR_RAG_HYDE": "0",
            "ORCHESTRATOR_RAG_RERANK": "0",
        },
    },
    {
        "name": "mq_hyde",
        "description": "Enable multi-query and HyDE without rerank",
        "env": {
            "ORCHESTRATOR_RAG_MULTI_QUERY": "1",
            "ORCHESTRATOR_RAG_HYDE": "1",
            "ORCHESTRATOR_RAG_RERANK": "0",
            "ORCHESTRATOR_RAG_MULTI_QUERY_COUNT": "3",
        },
    },
    {
        "name": "full_rag",
        "description": "Enable multi-query, HyDE and rerank",
        "env": {
            "ORCHESTRATOR_RAG_MULTI_QUERY": "1",
            "ORCHESTRATOR_RAG_HYDE": "1",
            "ORCHESTRATOR_RAG_RERANK": "1",
            "ORCHESTRATOR_RAG_MULTI_QUERY_COUNT": "3",
        },
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare RAG profiles with a shared offline dataset.")
    parser.add_argument("--dataset", required=True, help="Path to evaluation dataset json.")
    parser.add_argument("--profiles", default="", help="Optional profiles json path.")
    parser.add_argument("--db-path", default="scratch/eval-rag/compare/orchestrator.sqlite3")
    parser.add_argument("--kb-root", default="scratch/eval-rag/compare/knowledge_bases")
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--default-limit", type=int, default=8)
    parser.add_argument("--ks", default="1,3,5")
    parser.add_argument("--max-queries", type=int, default=0)
    parser.add_argument("--output-json", default="scratch/eval-rag/compare/profile_compare.json")
    parser.add_argument("--output-md", default="scratch/eval-rag/compare/profile_compare.md")
    return parser.parse_args()


def load_profiles(path: str) -> list[dict[str, Any]]:
    raw_path = str(path or "").strip()
    if not raw_path:
        return list(DEFAULT_PROFILES)
    profile_path = Path(raw_path).expanduser().resolve()
    if not profile_path.exists():
        raise FileNotFoundError(f"Profiles file not found: {profile_path}")
    raw = json.loads(profile_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        candidates = raw.get("profiles")
    else:
        candidates = raw
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Profiles file must contain a non-empty profile array.")
    output: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            raise ValueError("Each profile entry must be an object.")
        name = str(item.get("name") or "").strip()
        if not name:
            raise ValueError("Each profile must include non-empty `name`.")
        env = item.get("env")
        if not isinstance(env, dict):
            raise ValueError(f"Profile `{name}` must include env object.")
        normalized_env = {str(key): str(value) for key, value in env.items()}
        output.append(
            {
                "name": name,
                "description": str(item.get("description") or "").strip(),
                "env": normalized_env,
            }
        )
    return output


@contextmanager
def temporary_env(overrides: dict[str, str]) -> Iterator[None]:
    snapshot: dict[str, str | None] = {}
    for key, value in overrides.items():
        snapshot[key] = os.environ.get(key)
        os.environ[key] = value
    try:
        yield
    finally:
        for key, original in snapshot.items():
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original


def build_eval_args(
    *,
    args: argparse.Namespace,
    reuse_course_id: str,
    skip_queries: bool,
) -> SimpleNamespace:
    return SimpleNamespace(
        dataset=args.dataset,
        db_path=args.db_path,
        kb_root=args.kb_root,
        course_name="",
        course_description="",
        chunk_size=int(args.chunk_size),
        default_limit=int(args.default_limit),
        ks=args.ks,
        max_queries=int(args.max_queries),
        reuse_course_id=reuse_course_id,
        output="",
        skip_queries=skip_queries,
    )


def pick_best_profile(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not results:
        return None
    return sorted(
        results,
        key=lambda item: (
            float(item.get("metrics", {}).get("mrr", 0.0)),
            float(item.get("metrics", {}).get("recallAtK", {}).get("R@3", 0.0)),
            -float(item.get("metrics", {}).get("meanLatencyMs", 0.0)),
        ),
        reverse=True,
    )[0]


def render_markdown_table(results: list[dict[str, Any]]) -> str:
    lines = [
        "| Profile | MRR | R@1 | R@3 | R@5 | Mean Latency (ms) | Evaluated Queries |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in results:
        metrics = item.get("metrics", {})
        recall = metrics.get("recallAtK", {})
        lines.append(
            "| {name} | {mrr:.4f} | {r1:.4f} | {r3:.4f} | {r5:.4f} | {lat:.2f} | {count} |".format(
                name=str(item.get("name") or ""),
                mrr=float(metrics.get("mrr", 0.0)),
                r1=float(recall.get("R@1", 0.0)),
                r3=float(recall.get("R@3", 0.0)),
                r5=float(recall.get("R@5", 0.0)),
                lat=float(metrics.get("meanLatencyMs", 0.0)),
                count=int(metrics.get("totalQueries", 0)),
            )
        )
    return "\n".join(lines)


async def run_compare(args: argparse.Namespace) -> dict[str, Any]:
    profiles = load_profiles(args.profiles)

    ingest_args = build_eval_args(args=args, reuse_course_id="", skip_queries=True)
    ingest_result = await run_evaluation(ingest_args)
    course_id = str(ingest_result.get("courseId") or "")
    if not course_id:
        raise RuntimeError("Failed to create or resolve evaluation course id.")

    profile_results: list[dict[str, Any]] = []
    for profile in profiles:
        profile_name = str(profile["name"])
        env_overrides = dict(profile.get("env") or {})
        eval_args = build_eval_args(args=args, reuse_course_id=course_id, skip_queries=False)
        with temporary_env(env_overrides):
            output = await run_evaluation(eval_args)
        profile_results.append(
            {
                "name": profile_name,
                "description": str(profile.get("description") or ""),
                "env": env_overrides,
                "metrics": output.get("metrics", {}),
                "querySummary": output.get("queries", {}),
            }
        )

    best = pick_best_profile(profile_results)
    markdown_table = render_markdown_table(profile_results)
    return {
        "runAt": datetime.now(timezone.utc).isoformat(),
        "datasetPath": str(Path(args.dataset).expanduser().resolve()),
        "courseId": course_id,
        "ingestSummary": ingest_result.get("ingest", {}),
        "profiles": profile_results,
        "bestProfile": best,
        "tableMarkdown": markdown_table,
    }


def _save_output(path_text: str, content: str) -> Path:
    target = Path(path_text).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


async def main_async() -> None:
    args = parse_args()
    output = await run_compare(args)
    rendered_json = json.dumps(output, ensure_ascii=False, indent=2)
    print(rendered_json)
    print("\n" + output.get("tableMarkdown", ""))
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
