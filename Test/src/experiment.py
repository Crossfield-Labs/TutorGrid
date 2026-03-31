from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.datasets import load_breast_cancer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


CLASS_LABELS = ["Benign", "Malignant"]


@dataclass(frozen=True)
class ExperimentConfig:
    random_state: int = 42
    test_size: float = 0.2


def build_models(random_state: int) -> dict[str, object]:
    return {
        "Logistic Regression": LogisticRegression(
            max_iter=2000,
            random_state=random_state,
            solver="lbfgs",
        ),
        "Support Vector Machine": SVC(
            kernel="rbf",
            probability=True,
            random_state=random_state,
        ),
        "K-Nearest Neighbors": KNeighborsClassifier(n_neighbors=7),
        "Random Forest": RandomForestClassifier(
            n_estimators=300,
            random_state=random_state,
        ),
    }


def save_confusion_matrix_plot(
    matrix: np.ndarray, model_name: str, destination: Path
) -> None:
    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    display = ConfusionMatrixDisplay(
        confusion_matrix=matrix,
        display_labels=CLASS_LABELS,
    )
    display.plot(ax=ax, cmap="Blues", colorbar=False, values_format="d")
    ax.set_title(f"Confusion Matrix - {model_name}")
    fig.tight_layout()
    fig.savefig(destination, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_roc_curve_plot(
    roc_curves: dict[str, dict[str, list[float] | float]], destination: Path
) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    for model_name, curve in roc_curves.items():
        ax.plot(
            curve["fpr"],
            curve["tpr"],
            linewidth=2.0,
            label=f"{model_name} (AUC={curve['roc_auc']:.3f})",
        )
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1.2)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curves on the Test Set")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(destination, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_metric_comparison_plot(metrics_df: pd.DataFrame, destination: Path) -> None:
    chart_columns = ["accuracy", "precision", "recall", "f1", "roc_auc"]
    labels = [name.replace(" ", "\n") for name in metrics_df["model"]]
    positions = np.arange(len(metrics_df))
    width = 0.15

    fig, ax = plt.subplots(figsize=(10, 6))
    for idx, column in enumerate(chart_columns):
        offset = (idx - (len(chart_columns) - 1) / 2) * width
        ax.bar(
            positions + offset,
            metrics_df[column],
            width=width,
            label=column.upper() if column != "roc_auc" else "AUC",
        )

    ax.set_xticks(positions)
    ax.set_xticklabels(labels)
    ax.set_ylim(0.8, 1.01)
    ax.set_ylabel("Score")
    ax.set_title("Model Comparison Across Evaluation Metrics")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(ncol=3)
    fig.tight_layout()
    fig.savefig(destination, dpi=220, bbox_inches="tight")
    plt.close(fig)


def run_experiment(output_dir: Path, config: ExperimentConfig) -> dict[str, object]:
    np.random.seed(config.random_state)

    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    figure_dir = output_dir / "figures"
    pdf_dir = output_dir / "pdf"
    for directory in (data_dir, figure_dir, pdf_dir):
        directory.mkdir(parents=True, exist_ok=True)

    dataset = load_breast_cancer(as_frame=True)
    features = dataset.data
    raw_target = dataset.target

    # Convert to an intuitive target definition: 1 means malignant, 0 means benign.
    target = raw_target.map({0: 1, 1: 0}).astype(int)

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=config.test_size,
        stratify=target,
        random_state=config.random_state,
    )

    dataset_info = {
        "dataset_name": "Breast Cancer Wisconsin Diagnostic",
        "source": "sklearn.datasets.load_breast_cancer",
        "samples": int(features.shape[0]),
        "features": int(features.shape[1]),
        "target_definition": {
            "0": "Benign",
            "1": "Malignant",
        },
        "class_distribution": {
            "benign": int((target == 0).sum()),
            "malignant": int((target == 1).sum()),
        },
        "feature_examples": features.columns[:5].tolist(),
    }

    split_info = {
        "train_samples": int(len(x_train)),
        "test_samples": int(len(x_test)),
        "train_distribution": {
            "benign": int((y_train == 0).sum()),
            "malignant": int((y_train == 1).sum()),
        },
        "test_distribution": {
            "benign": int((y_test == 0).sum()),
            "malignant": int((y_test == 1).sum()),
        },
        "random_state": config.random_state,
        "test_size": config.test_size,
        "standardization": "StandardScaler fitted on the training split only",
    }

    detailed_results: dict[str, dict[str, object]] = {}
    roc_curves: dict[str, dict[str, list[float] | float]] = {}
    records: list[dict[str, float | str]] = []
    confusion_matrix_paths: dict[str, str] = {}

    for model_name, estimator in build_models(config.random_state).items():
        pipeline = Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                ("model", estimator),
            ]
        )
        pipeline.fit(x_train, y_train)

        predictions = pipeline.predict(x_test)
        probabilities = pipeline.predict_proba(x_test)[:, 1]

        matrix = confusion_matrix(y_test, predictions, labels=[0, 1])
        fpr, tpr, _ = roc_curve(y_test, probabilities, pos_label=1)
        auc_value = roc_auc_score(y_test, probabilities)

        result = {
            "model": model_name,
            "accuracy": float(accuracy_score(y_test, predictions)),
            "precision": float(
                precision_score(y_test, predictions, pos_label=1, zero_division=0)
            ),
            "recall": float(
                recall_score(y_test, predictions, pos_label=1, zero_division=0)
            ),
            "f1": float(f1_score(y_test, predictions, pos_label=1, zero_division=0)),
            "roc_auc": float(auc_value),
        }
        records.append(result)

        confusion_path = figure_dir / (
            f"confusion_matrix_{model_name.lower().replace(' ', '_')}.png"
        )
        save_confusion_matrix_plot(matrix=matrix, model_name=model_name, destination=confusion_path)
        confusion_matrix_paths[model_name] = str(confusion_path.resolve())

        detailed_results[model_name] = {
            **result,
            "confusion_matrix": matrix.astype(int).tolist(),
            "roc_curve": {
                "fpr": [float(value) for value in fpr],
                "tpr": [float(value) for value in tpr],
            },
            "artifacts": {
                "confusion_matrix_png": str(confusion_path.resolve()),
            },
        }
        roc_curves[model_name] = {
            "fpr": [float(value) for value in fpr],
            "tpr": [float(value) for value in tpr],
            "roc_auc": float(auc_value),
        }

    metrics_df = pd.DataFrame(records).sort_values(
        by=["f1", "roc_auc", "accuracy"],
        ascending=False,
    )
    best_model = str(metrics_df.iloc[0]["model"])

    metrics_csv = data_dir / "model_metrics.csv"
    metrics_json = data_dir / "model_metrics.json"
    summary_json = data_dir / "experiment_summary.json"
    roc_path = figure_dir / "roc_curves.png"
    comparison_path = figure_dir / "metric_comparison.png"

    metrics_df.to_csv(metrics_csv, index=False, encoding="utf-8-sig")
    metrics_json.write_text(
        metrics_df.to_json(orient="records", force_ascii=False, indent=2),
        encoding="utf-8",
    )

    save_roc_curve_plot(roc_curves=roc_curves, destination=roc_path)
    save_metric_comparison_plot(metrics_df=metrics_df, destination=comparison_path)

    summary = {
        "dataset": dataset_info,
        "split": split_info,
        "best_model": best_model,
        "results": detailed_results,
        "ranking": json.loads(metrics_df.to_json(orient="records", force_ascii=False)),
        "artifacts": {
            "output_dir": str(output_dir.resolve()),
            "metrics_csv": str(metrics_csv.resolve()),
            "metrics_json": str(metrics_json.resolve()),
            "roc_curve": str(roc_path.resolve()),
            "metric_comparison": str(comparison_path.resolve()),
            "confusion_matrices": confusion_matrix_paths,
            "report_pdf": "",
        },
    }

    summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary
