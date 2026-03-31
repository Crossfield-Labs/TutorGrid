from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from textwrap import dedent

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

import matplotlib
import joblib
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sklearn.datasets import load_breast_cancer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    auc,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
FIGURES_DIR = OUTPUT_DIR / "figures"
RESULTS_DIR = OUTPUT_DIR / "results"
PDF_DIR = OUTPUT_DIR / "pdf"
TMP_PDF_DIR = ROOT / "tmp" / "pdfs"

RANDOM_STATE = 42
TEST_SIZE = 0.2
POSITIVE_CLASS_NAME = "Malignant"
NEGATIVE_CLASS_NAME = "Benign"


def ensure_dirs() -> None:
    for directory in [FIGURES_DIR, RESULTS_DIR, PDF_DIR, TMP_PDF_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def load_dataset() -> tuple[pd.DataFrame, pd.Series, dict[str, object]]:
    dataset = load_breast_cancer(as_frame=True)
    features = dataset.data.copy()

    # Re-map labels so malignant is the positive class for medical relevance.
    target = (dataset.target == 0).astype(int)
    target.name = "malignant"

    dataset_info = {
        "dataset_name": "Breast Cancer Wisconsin Diagnostic",
        "sample_count": int(features.shape[0]),
        "feature_count": int(features.shape[1]),
        "class_distribution": {
            POSITIVE_CLASS_NAME: int(target.sum()),
            NEGATIVE_CLASS_NAME: int((target == 0).sum()),
        },
        "feature_names": dataset.feature_names.tolist(),
    }
    return features, target, dataset_info


def build_models() -> dict[str, Pipeline]:
    return {
        "Logistic Regression": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        max_iter=5000,
                        solver="liblinear",
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
        "SVM (RBF Kernel)": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "model",
                    SVC(
                        kernel="rbf",
                        probability=True,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
        "Random Forest": Pipeline(
            [
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=300,
                        random_state=RANDOM_STATE,
                        n_jobs=1,
                    ),
                ),
            ]
        ),
        "KNN": Pipeline(
            [
                ("scaler", StandardScaler()),
                ("model", KNeighborsClassifier(n_neighbors=7)),
            ]
        ),
    }


def evaluate_models(
    models: dict[str, Pipeline],
    x_train: pd.DataFrame,
    x_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
) -> tuple[pd.DataFrame, dict[str, dict[str, object]]]:
    metrics_rows: list[dict[str, float | str]] = []
    details: dict[str, dict[str, object]] = {}

    for name, pipeline in models.items():
        pipeline.fit(x_train, y_train)

        train_predictions = pipeline.predict(x_train)
        test_predictions = pipeline.predict(x_test)
        test_probabilities = pipeline.predict_proba(x_test)[:, 1]

        accuracy = accuracy_score(y_test, test_predictions)
        precision = precision_score(y_test, test_predictions, zero_division=0)
        recall = recall_score(y_test, test_predictions, zero_division=0)
        f1 = f1_score(y_test, test_predictions, zero_division=0)
        fpr, tpr, thresholds = roc_curve(y_test, test_probabilities)
        roc_auc = auc(fpr, tpr)
        matrix = confusion_matrix(y_test, test_predictions, labels=[1, 0])

        metrics_rows.append(
            {
                "model": name,
                "train_accuracy": accuracy_score(y_train, train_predictions),
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "auc": roc_auc,
            }
        )

        roc_frame = pd.DataFrame(
            {
                "fpr": fpr,
                "tpr": tpr,
                "threshold": np.append(thresholds[:-1], np.nan),
            }
        )
        roc_frame.to_csv(RESULTS_DIR / f"roc_points_{slugify(name)}.csv", index=False)

        matrix_frame = pd.DataFrame(
            matrix,
            index=[f"Actual {POSITIVE_CLASS_NAME}", f"Actual {NEGATIVE_CLASS_NAME}"],
            columns=[
                f"Predicted {POSITIVE_CLASS_NAME}",
                f"Predicted {NEGATIVE_CLASS_NAME}",
            ],
        )
        matrix_frame.to_csv(
            RESULTS_DIR / f"confusion_matrix_{slugify(name)}.csv",
            encoding="utf-8-sig",
        )

        details[name] = {
            "pipeline": pipeline,
            "predictions": test_predictions.tolist(),
            "probabilities": test_probabilities.tolist(),
            "confusion_matrix": matrix.tolist(),
            "roc_auc": float(roc_auc),
            "roc_curve": {
                "fpr": fpr.tolist(),
                "tpr": tpr.tolist(),
                "thresholds": thresholds.tolist(),
            },
        }

    metrics_df = pd.DataFrame(metrics_rows).sort_values(
        by=["f1", "accuracy", "auc"],
        ascending=False,
    )
    metrics_df.reset_index(drop=True, inplace=True)
    return metrics_df, details


def slugify(name: str) -> str:
    return (
        name.lower()
        .replace(" ", "_")
        .replace("(", "")
        .replace(")", "")
        .replace("-", "_")
    )


def plot_metric_comparison(metrics_df: pd.DataFrame) -> Path:
    metric_columns = ["accuracy", "precision", "recall", "f1", "auc"]
    models = metrics_df["model"].tolist()
    x_positions = np.arange(len(models))
    width = 0.15

    fig, axis = plt.subplots(figsize=(12, 6.8))
    colors_list = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

    for index, metric in enumerate(metric_columns):
        values = metrics_df[metric].to_numpy()
        axis.bar(
            x_positions + (index - 2) * width,
            values,
            width=width,
            label=metric.upper(),
            color=colors_list[index],
        )

    axis.set_ylim(0.85, 1.01)
    axis.set_xticks(x_positions)
    axis.set_xticklabels(models, rotation=15, ha="right")
    axis.set_ylabel("Score")
    axis.set_title("Model Performance Comparison on Test Set")
    axis.legend(ncols=3)
    axis.grid(axis="y", linestyle="--", alpha=0.4)

    for index, row in metrics_df.iterrows():
        axis.text(
            x_positions[index],
            row["f1"] + 0.004,
            f"F1={row['f1']:.3f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    fig.tight_layout()
    output_path = FIGURES_DIR / "model_metric_comparison.png"
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_roc_curves(metrics_df: pd.DataFrame, details: dict[str, dict[str, object]]) -> Path:
    fig, axis = plt.subplots(figsize=(10.5, 8))
    palette = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#8c564b"]

    for color, row in zip(palette, metrics_df.itertuples(index=False)):
        roc_data = details[row.model]["roc_curve"]
        axis.plot(
            roc_data["fpr"],
            roc_data["tpr"],
            linewidth=2.2,
            color=color,
            label=f"{row.model} (AUC={row.auc:.4f})",
        )

    axis.plot([0, 1], [0, 1], linestyle="--", color="#666666", linewidth=1.3)
    axis.set_title("ROC Curves")
    axis.set_xlabel("False Positive Rate")
    axis.set_ylabel("True Positive Rate")
    axis.legend(loc="lower right")
    axis.grid(linestyle="--", alpha=0.35)
    fig.tight_layout()

    output_path = FIGURES_DIR / "roc_curves.png"
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_confusion_matrices(
    metrics_df: pd.DataFrame,
    details: dict[str, dict[str, object]],
) -> tuple[list[Path], Path]:
    individual_paths: list[Path] = []
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 9.5), constrained_layout=True)
    axes = axes.flatten()

    for axis, row in zip(axes, metrics_df.itertuples(index=False)):
        matrix = np.array(details[row.model]["confusion_matrix"])
        image = axis.imshow(matrix, cmap="Blues")
        axis.set_title(row.model)
        axis.set_xticks([0, 1])
        axis.set_yticks([0, 1])
        axis.set_xticklabels([POSITIVE_CLASS_NAME, NEGATIVE_CLASS_NAME], rotation=15)
        axis.set_yticklabels([POSITIVE_CLASS_NAME, NEGATIVE_CLASS_NAME])
        axis.set_xlabel("Predicted Label")
        axis.set_ylabel("True Label")

        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                axis.text(
                    j,
                    i,
                    str(matrix[i, j]),
                    ha="center",
                    va="center",
                    color="black",
                    fontsize=12,
                    fontweight="bold",
                )

        single_fig, single_axis = plt.subplots(figsize=(4.8, 4.4))
        single_axis.imshow(matrix, cmap="Blues")
        single_axis.set_title(f"Confusion Matrix - {row.model}")
        single_axis.set_xticks([0, 1])
        single_axis.set_yticks([0, 1])
        single_axis.set_xticklabels([POSITIVE_CLASS_NAME, NEGATIVE_CLASS_NAME], rotation=15)
        single_axis.set_yticklabels([POSITIVE_CLASS_NAME, NEGATIVE_CLASS_NAME])
        single_axis.set_xlabel("Predicted Label")
        single_axis.set_ylabel("True Label")
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                single_axis.text(
                    j,
                    i,
                    str(matrix[i, j]),
                    ha="center",
                    va="center",
                    color="black",
                    fontsize=12,
                    fontweight="bold",
                )
        single_fig.colorbar(single_axis.images[0], ax=single_axis, fraction=0.046, pad=0.04)
        single_fig.tight_layout()
        single_path = FIGURES_DIR / f"confusion_matrix_{slugify(row.model)}.png"
        single_fig.savefig(single_path, dpi=220, bbox_inches="tight")
        plt.close(single_fig)
        individual_paths.append(single_path)

    fig.colorbar(image, ax=axes.tolist(), fraction=0.025, pad=0.02)
    fig.suptitle("Confusion Matrices Across Models", fontsize=16)
    grid_path = FIGURES_DIR / "confusion_matrices_grid.png"
    fig.savefig(grid_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return individual_paths, grid_path


def plot_random_forest_importance(
    feature_names: list[str],
    model_pipeline: Pipeline,
) -> Path:
    forest = model_pipeline.named_steps["model"]
    importance_series = pd.Series(
        forest.feature_importances_,
        index=feature_names,
    ).sort_values(ascending=False).head(12)

    fig, axis = plt.subplots(figsize=(10.5, 7.2))
    importance_series.sort_values().plot.barh(ax=axis, color="#2ca02c")
    axis.set_title("Top 12 Feature Importances from Random Forest")
    axis.set_xlabel("Importance")
    axis.set_ylabel("Feature")
    axis.grid(axis="x", linestyle="--", alpha=0.35)
    fig.tight_layout()

    output_path = FIGURES_DIR / "random_forest_feature_importance.png"
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output_path


def export_metrics(
    metrics_df: pd.DataFrame,
    dataset_info: dict[str, object],
    x_train: pd.DataFrame,
    x_test: pd.DataFrame,
) -> None:
    metrics_df.to_csv(RESULTS_DIR / "metrics_summary.csv", index=False, encoding="utf-8-sig")

    metadata = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": dataset_info,
        "split": {
            "train_size": int(len(x_train)),
            "test_size": int(len(x_test)),
            "test_ratio": TEST_SIZE,
            "random_state": RANDOM_STATE,
        },
        "evaluation_target": POSITIVE_CLASS_NAME,
    }

    with open(RESULTS_DIR / "experiment_metadata.json", "w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)


def build_key_findings(metrics_df: pd.DataFrame) -> list[str]:
    best = metrics_df.iloc[0]
    second = metrics_df.iloc[1]
    findings = [
        (
            f"Best overall model: {best['model']}, "
            f"with accuracy={best['accuracy']:.4f}, precision={best['precision']:.4f}, "
            f"recall={best['recall']:.4f}, f1={best['f1']:.4f}, auc={best['auc']:.4f}."
        ),
        (
            f"Compared with the runner-up {second['model']}, the best model improves "
            f"F1 score by {(best['f1'] - second['f1']):.4f}."
        ),
        (
            "The data split is stratified and feature scaling is applied within the "
            "training pipeline, preventing test-set leakage."
        ),
    ]
    return findings


def save_text_summary(metrics_df: pd.DataFrame, dataset_info: dict[str, object]) -> Path:
    best = metrics_df.iloc[0]
    findings = build_key_findings(metrics_df)
    content = dedent(
        f"""
        # Breast Cancer ML Lab Summary

        Generated at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

        ## Dataset
        - Name: {dataset_info['dataset_name']}
        - Samples: {dataset_info['sample_count']}
        - Features: {dataset_info['feature_count']}
        - Positive class: {POSITIVE_CLASS_NAME}
        - Negative class: {NEGATIVE_CLASS_NAME}

        ## Best Model
        - Model: {best['model']}
        - Accuracy: {best['accuracy']:.4f}
        - Precision: {best['precision']:.4f}
        - Recall: {best['recall']:.4f}
        - F1: {best['f1']:.4f}
        - AUC: {best['auc']:.4f}

        ## Key Findings
        - {findings[0]}
        - {findings[1]}
        - {findings[2]}
        """
    ).strip()

    summary_path = RESULTS_DIR / "summary.md"
    summary_path.write_text(content, encoding="utf-8")
    return summary_path


def save_best_model(model_name: str, pipeline: Pipeline) -> Path:
    model_path = RESULTS_DIR / f"best_model_{slugify(model_name)}.joblib"
    joblib.dump(pipeline, model_path)
    return model_path


def build_report(
    metrics_df: pd.DataFrame,
    dataset_info: dict[str, object],
    figure_paths: dict[str, Path],
) -> Path:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

    report_path = PDF_DIR / "breast_cancer_ml_experiment_report.pdf"
    document = SimpleDocTemplate(
        str(report_path),
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.5 * cm,
        title="机器学习课程实验报告",
        author="Codex",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CNTitle",
        parent=styles["Title"],
        fontName="STSong-Light",
        fontSize=20,
        leading=28,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1d3557"),
    )
    heading_style = ParagraphStyle(
        "CNHeading",
        parent=styles["Heading2"],
        fontName="STSong-Light",
        fontSize=14,
        leading=22,
        textColor=colors.HexColor("#0b6e4f"),
        spaceBefore=6,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "CNBody",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=10.8,
        leading=18,
        alignment=TA_LEFT,
    )
    note_style = ParagraphStyle(
        "CNNote",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=9.5,
        leading=15,
        textColor=colors.HexColor("#444444"),
    )

    best = metrics_df.iloc[0]
    findings = build_key_findings(metrics_df)

    story = [
        Paragraph("机器学习课程实验报告", title_style),
        Spacer(1, 0.4 * cm),
        Paragraph("实验题目：基于 Breast Cancer Wisconsin 数据集的乳腺癌分类对比实验", body_style),
        Paragraph(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", body_style),
        Paragraph("报告类型：自动生成课程风格实验报告", body_style),
        Spacer(1, 0.45 * cm),
    ]

    intro_table = Table(
        [
            ["数据集", dataset_info["dataset_name"]],
            ["样本数", str(dataset_info["sample_count"])],
            ["特征数", str(dataset_info["feature_count"])],
            [
                "类别分布",
                f"恶性 {dataset_info['class_distribution'][POSITIVE_CLASS_NAME]}，"
                f"良性 {dataset_info['class_distribution'][NEGATIVE_CLASS_NAME]}",
            ],
            ["实验模型", "Logistic Regression, SVM, Random Forest, KNN"],
            ["数据处理", "训练/测试划分 + 基于训练集拟合的标准化"],
        ],
        colWidths=[3.2 * cm, 12.8 * cm],
    )
    intro_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("FONTSIZE", (0, 0), (-1, -1), 10.5),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8f1f2")),
                ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#98c1d9")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([intro_table, Spacer(1, 0.35 * cm)])

    story.extend(
        [
            Paragraph("一、实验目标与方法", heading_style),
            Paragraph(
                "本实验基于 scikit-learn 自带的乳腺癌诊断数据集，完成一个从数据加载、"
                "训练/测试划分、标准化、模型训练、性能评估，到图表与 PDF 报告自动生成的完整流程。"
                "为了便于医学场景解释，实验将“恶性”定义为正类。",
                body_style,
            ),
            Paragraph(
                "建模阶段比较了 Logistic Regression、SVM（RBF 核）、Random Forest 和 KNN 四类传统机器学习方法。"
                "其中涉及距离或线性决策边界的模型均通过 Pipeline 在训练集上拟合 StandardScaler，再应用到测试集，"
                "从而避免测试集信息泄露。",
                body_style,
            ),
            Paragraph("二、实验结果总览", heading_style),
        ]
    )

    result_table_rows = [
        ["模型", "Train Acc", "Accuracy", "Precision", "Recall", "F1", "AUC"]
    ]
    for row in metrics_df.itertuples(index=False):
        result_table_rows.append(
            [
                row.model,
                f"{row.train_accuracy:.4f}",
                f"{row.accuracy:.4f}",
                f"{row.precision:.4f}",
                f"{row.recall:.4f}",
                f"{row.f1:.4f}",
                f"{row.auc:.4f}",
            ]
        )

    results_table = Table(
        result_table_rows,
        colWidths=[4.1 * cm, 2 * cm, 2 * cm, 2 * cm, 2 * cm, 1.7 * cm, 1.7 * cm],
    )
    results_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.4),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b6e4f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fbfc")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#a9bcd0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend(
        [
            results_table,
            Spacer(1, 0.25 * cm),
            Paragraph(
                f"综合 F1、Accuracy 与 AUC 指标，最佳模型为 {best['model']}。"
                f"其测试集 Accuracy={best['accuracy']:.4f}，Recall={best['recall']:.4f}，AUC={best['auc']:.4f}。",
                body_style,
            ),
            Spacer(1, 0.2 * cm),
            Paragraph("图 1 模型指标对比", note_style),
            fit_image(figure_paths["comparison"], max_width=17 * cm, max_height=8.3 * cm),
            Paragraph("图 2 ROC 曲线", note_style),
            fit_image(figure_paths["roc"], max_width=16.5 * cm, max_height=8 * cm),
            PageBreak(),
            Paragraph("三、混淆矩阵与特征分析", heading_style),
            Paragraph(
                "混淆矩阵按照“恶性、良性”的顺序展示真实标签与预测标签。"
                "从图中可以直观看到不同模型在恶性样本识别上的错分情况。",
                body_style,
            ),
            Paragraph("图 3 不同模型的混淆矩阵", note_style),
            fit_image(figure_paths["confusion_grid"], max_width=17 * cm, max_height=11.8 * cm),
            Spacer(1, 0.15 * cm),
            Paragraph(
                "为了补充解释性，本实验额外输出了 Random Forest 的特征重要性排序图。"
                "可见若干半径、周长、面积和凹陷相关特征对分类决策影响更大。",
                body_style,
            ),
            Paragraph("图 4 Random Forest 特征重要性", note_style),
            fit_image(figure_paths["feature_importance"], max_width=16.2 * cm, max_height=8.2 * cm),
            Paragraph("四、关键结论", heading_style),
            Paragraph(f"1. {findings[0]}", body_style),
            Paragraph(f"2. {findings[1]}", body_style),
            Paragraph(f"3. {findings[2]}", body_style),
            Paragraph(
                "4. 从训练准确率与测试准确率的对比来看，Random Forest 的训练集拟合程度最高，"
                "但并不一定带来最优的泛化表现；对于本数据集，经过标准化后的边界型模型表现更稳健。",
                body_style,
            ),
            Paragraph("五、实验结论与可扩展方向", heading_style),
            Paragraph(
                "本实验已经完成课程作业要求的完整闭环：内置数据集加载、预处理、多模型对比、"
                "指标保存、图表输出、最佳模型总结以及 PDF 报告自动导出。后续可继续扩展交叉验证、"
                "超参数搜索、特征选择与模型解释方法，以形成更完整的实验平台。",
                body_style,
            ),
        ]
    )

    document.build(story, onFirstPage=draw_page_number, onLaterPages=draw_page_number)
    return report_path


def fit_image(path: Path, max_width: float, max_height: float) -> Image:
    image = Image(str(path))
    image.drawWidth, image.drawHeight = scale_dimensions(
        image.imageWidth,
        image.imageHeight,
        max_width,
        max_height,
    )
    return image


def scale_dimensions(width: float, height: float, max_width: float, max_height: float) -> tuple[float, float]:
    ratio = min(max_width / width, max_height / height)
    return width * ratio, height * ratio


def draw_page_number(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawRightString(19.1 * cm, 1.0 * cm, f"Page {doc.page}")
    canvas.restoreState()


def save_manifest(
    metrics_df: pd.DataFrame,
    summary_path: Path,
    report_path: Path,
    best_model_path: Path,
    figure_paths: dict[str, Path],
) -> Path:
    best = metrics_df.iloc[0]
    manifest = {
        "best_model": {
            "name": best["model"],
            "accuracy": float(best["accuracy"]),
            "precision": float(best["precision"]),
            "recall": float(best["recall"]),
            "f1": float(best["f1"]),
            "auc": float(best["auc"]),
        },
        "files": {
            "summary_markdown": str(summary_path),
            "report_pdf": str(report_path),
            "best_model_joblib": str(best_model_path),
            "metrics_csv": str(RESULTS_DIR / "metrics_summary.csv"),
            "metadata_json": str(RESULTS_DIR / "experiment_metadata.json"),
            "comparison_plot": str(figure_paths["comparison"]),
            "roc_plot": str(figure_paths["roc"]),
            "confusion_grid_plot": str(figure_paths["confusion_grid"]),
            "feature_importance_plot": str(figure_paths["feature_importance"]),
        },
    }

    manifest_path = RESULTS_DIR / "artifact_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)
    return manifest_path


def main() -> None:
    ensure_dirs()
    x, y, dataset_info = load_dataset()

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=TEST_SIZE,
        stratify=y,
        random_state=RANDOM_STATE,
    )

    models = build_models()
    metrics_df, details = evaluate_models(models, x_train, x_test, y_train, y_test)

    export_metrics(metrics_df, dataset_info, x_train, x_test)
    comparison_path = plot_metric_comparison(metrics_df)
    roc_path = plot_roc_curves(metrics_df, details)
    _, confusion_grid_path = plot_confusion_matrices(metrics_df, details)
    feature_importance_path = plot_random_forest_importance(
        dataset_info["feature_names"],
        details["Random Forest"]["pipeline"],
    )

    best_model_name = metrics_df.iloc[0]["model"]
    best_model_path = save_best_model(best_model_name, details[best_model_name]["pipeline"])
    summary_path = save_text_summary(metrics_df, dataset_info)
    report_path = build_report(
        metrics_df,
        dataset_info,
        {
            "comparison": comparison_path,
            "roc": roc_path,
            "confusion_grid": confusion_grid_path,
            "feature_importance": feature_importance_path,
        },
    )
    manifest_path = save_manifest(
        metrics_df,
        summary_path,
        report_path,
        best_model_path,
        {
            "comparison": comparison_path,
            "roc": roc_path,
            "confusion_grid": confusion_grid_path,
            "feature_importance": feature_importance_path,
        },
    )

    print("Experiment completed successfully.")
    print(f"Best model: {best_model_name}")
    print(metrics_df.to_string(index=False))
    print(f"Report: {report_path}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
