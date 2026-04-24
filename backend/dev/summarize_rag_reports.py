from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize RAG compare/grid reports into a recommendation brief.")
    parser.add_argument(
        "--profile-report",
        default="scratch/eval-rag/compare/profile_compare.json",
        help="Path to profile compare json report.",
    )
    parser.add_argument(
        "--grid-report",
        default="scratch/eval-rag/grid/tune_report.json",
        help="Path to grid tuning json report.",
    )
    parser.add_argument(
        "--output-md",
        default="scratch/eval-rag/recommendation.md",
        help="Output markdown report path.",
    )
    parser.add_argument(
        "--output-json",
        default="scratch/eval-rag/recommendation.json",
        help="Output machine-readable summary path.",
    )
    return parser.parse_args()


def _load_json(path_text: str) -> dict[str, Any]:
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Report does not exist: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Report root must be json object: {path}")
    return raw


def _safe_metric(metrics: dict[str, Any], key: str) -> float:
    return float(metrics.get(key, 0.0))


def _safe_recall(metrics: dict[str, Any], key: str) -> float:
    recall = metrics.get("recallAtK", {})
    if not isinstance(recall, dict):
        return 0.0
    return float(recall.get(key, 0.0))


def _find_profile(results: list[dict[str, Any]], profile_name: str) -> dict[str, Any] | None:
    target = profile_name.strip().lower()
    for item in results:
        if str(item.get("name") or "").strip().lower() == target:
            return item
    return None


def _delta_text(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.4f}"


def build_recommendation(profile_report: dict[str, Any], grid_report: dict[str, Any]) -> dict[str, Any]:
    profile_results = profile_report.get("profiles")
    if not isinstance(profile_results, list):
        profile_results = []
    best_profile = profile_report.get("bestProfile")
    if not isinstance(best_profile, dict):
        best_profile = {}

    grid_best = grid_report.get("best")
    if not isinstance(grid_best, dict):
        grid_best = {}
    variants = grid_report.get("variants")
    if not isinstance(variants, list):
        variants = []

    baseline = _find_profile(profile_results, "baseline") or {}
    full_rag = _find_profile(profile_results, "full_rag") or {}
    best_profile_name = str(best_profile.get("name") or "")
    best_chunk = int(grid_best.get("chunkSize") or 0)
    best_grid_profile = str(grid_best.get("profile") or "")

    best_profile_metrics = best_profile.get("metrics", {}) if isinstance(best_profile.get("metrics"), dict) else {}
    baseline_metrics = baseline.get("metrics", {}) if isinstance(baseline.get("metrics"), dict) else {}
    full_metrics = full_rag.get("metrics", {}) if isinstance(full_rag.get("metrics"), dict) else {}
    grid_best_metrics = grid_best.get("metrics", {}) if isinstance(grid_best.get("metrics"), dict) else {}

    profile_delta_mrr = _safe_metric(best_profile_metrics, "mrr") - _safe_metric(baseline_metrics, "mrr")
    profile_delta_r3 = _safe_recall(best_profile_metrics, "R@3") - _safe_recall(baseline_metrics, "R@3")
    profile_delta_latency = _safe_metric(best_profile_metrics, "meanLatencyMs") - _safe_metric(baseline_metrics, "meanLatencyMs")
    full_delta_mrr = _safe_metric(full_metrics, "mrr") - _safe_metric(baseline_metrics, "mrr")
    full_delta_latency = _safe_metric(full_metrics, "meanLatencyMs") - _safe_metric(baseline_metrics, "meanLatencyMs")

    recommendation = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "datasetPath": str(profile_report.get("datasetPath") or grid_report.get("datasetPath") or ""),
        "recommended": {
            "chunkSize": best_chunk,
            "profile": best_grid_profile or best_profile_name,
            "score": float(grid_best.get("score") or 0.0),
            "mrr": _safe_metric(grid_best_metrics, "mrr"),
            "recallAt3": _safe_recall(grid_best_metrics, "R@3"),
            "latencyMs": _safe_metric(grid_best_metrics, "meanLatencyMs"),
        },
        "profileSummary": {
            "bestProfile": best_profile_name,
            "bestVsBaseline": {
                "deltaMRR": profile_delta_mrr,
                "deltaR3": profile_delta_r3,
                "deltaLatencyMs": profile_delta_latency,
            },
            "fullRagVsBaseline": {
                "deltaMRR": full_delta_mrr,
                "deltaLatencyMs": full_delta_latency,
            },
        },
        "variantCount": len(variants),
        "topVariants": variants[:5],
    }
    return recommendation


def render_markdown(summary: dict[str, Any]) -> str:
    recommended = summary.get("recommended", {})
    profile_summary = summary.get("profileSummary", {})
    best_vs_baseline = profile_summary.get("bestVsBaseline", {})
    full_vs_baseline = profile_summary.get("fullRagVsBaseline", {})
    top_variants = summary.get("topVariants", [])
    if not isinstance(top_variants, list):
        top_variants = []

    lines = [
        "# RAG Tuning Recommendation",
        "",
        f"- Generated at: `{summary.get('generatedAt', '')}`",
        f"- Dataset: `{summary.get('datasetPath', '')}`",
        "",
        "## Recommended Default",
        "",
        f"- Chunk size: `{int(recommended.get('chunkSize') or 0)}`",
        f"- Profile: `{recommended.get('profile', '')}`",
        f"- Score: `{float(recommended.get('score') or 0.0):.3f}`",
        f"- MRR: `{float(recommended.get('mrr') or 0.0):.4f}`",
        f"- R@3: `{float(recommended.get('recallAt3') or 0.0):.4f}`",
        f"- Mean latency (ms): `{float(recommended.get('latencyMs') or 0.0):.2f}`",
        "",
        "## Profile Comparison Notes",
        "",
        f"- Best vs baseline MRR: `{_delta_text(float(best_vs_baseline.get('deltaMRR') or 0.0))}`",
        f"- Best vs baseline R@3: `{_delta_text(float(best_vs_baseline.get('deltaR3') or 0.0))}`",
        f"- Best vs baseline latency (ms): `{_delta_text(float(best_vs_baseline.get('deltaLatencyMs') or 0.0))}`",
        f"- Full RAG vs baseline MRR: `{_delta_text(float(full_vs_baseline.get('deltaMRR') or 0.0))}`",
        f"- Full RAG vs baseline latency (ms): `{_delta_text(float(full_vs_baseline.get('deltaLatencyMs') or 0.0))}`",
        "",
        "## Top Variants",
        "",
        "| Rank | Chunk Size | Profile | Score | MRR | R@3 | Latency (ms) |",
        "|---:|---:|---|---:|---:|---:|---:|",
    ]
    for idx, item in enumerate(top_variants, start=1):
        metrics = item.get("metrics", {})
        recall = metrics.get("recallAtK", {}) if isinstance(metrics, dict) else {}
        lines.append(
            "| {rank} | {chunk} | {profile} | {score:.3f} | {mrr:.4f} | {r3:.4f} | {lat:.2f} |".format(
                rank=idx,
                chunk=int(item.get("chunkSize") or 0),
                profile=str(item.get("profile") or ""),
                score=float(item.get("score") or 0.0),
                mrr=float(metrics.get("mrr") or 0.0) if isinstance(metrics, dict) else 0.0,
                r3=float(recall.get("R@3") or 0.0) if isinstance(recall, dict) else 0.0,
                lat=float(metrics.get("meanLatencyMs") or 0.0) if isinstance(metrics, dict) else 0.0,
            )
        )
    return "\n".join(lines) + "\n"


def _save_text(path_text: str, content: str) -> Path:
    target = Path(path_text).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def main() -> None:
    args = parse_args()
    profile_report = _load_json(args.profile_report)
    grid_report = _load_json(args.grid_report)
    summary = build_recommendation(profile_report=profile_report, grid_report=grid_report)
    markdown = render_markdown(summary)
    rendered_json = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    json_path = _save_text(args.output_json, rendered_json)
    md_path = _save_text(args.output_md, markdown)
    print(rendered_json)
    print(markdown)
    print(f"[saved-json] {json_path}")
    print(f"[saved-md] {md_path}")


if __name__ == "__main__":
    main()
