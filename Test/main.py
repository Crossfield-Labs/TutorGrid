from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.experiment import ExperimentConfig, run_experiment
from src.report import generate_course_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Breast Cancer Wisconsin Diagnostic binary classification course experiment"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory used to store generated figures, tables, and the PDF report.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed used for dataset splitting and model training.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Proportion of the dataset reserved for the test split.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output_dir = args.output_dir.resolve()

    config = ExperimentConfig(
        random_state=args.random_state,
        test_size=args.test_size,
    )
    summary = run_experiment(output_dir=output_dir, config=config)

    report_path = output_dir / "pdf" / "breast_cancer_course_report.pdf"
    generate_course_report(summary=summary, output_path=report_path)

    summary["artifacts"]["report_pdf"] = str(report_path.resolve())
    summary_path = output_dir / "data" / "experiment_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    best = summary["best_model"]
    best_metrics = summary["results"][best]
    print("Experiment completed successfully.")
    print(f"Best model: {best}")
    print(
        "Key metrics "
        f"(Accuracy={best_metrics['accuracy']:.4f}, "
        f"Precision={best_metrics['precision']:.4f}, "
        f"Recall={best_metrics['recall']:.4f}, "
        f"F1={best_metrics['f1']:.4f}, "
        f"AUC={best_metrics['roc_auc']:.4f})"
    )
    print(f"Metrics table: {summary['artifacts']['metrics_csv']}")
    print(f"ROC curve: {summary['artifacts']['roc_curve']}")
    print(f"PDF report: {summary['artifacts']['report_pdf']}")


if __name__ == "__main__":
    main()
