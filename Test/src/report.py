from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
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


PAGE_WIDTH, PAGE_HEIGHT = A4
CONTENT_WIDTH = PAGE_WIDTH - 2 * cm


def register_fonts() -> str:
    font_name = "STSong-Light"
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))
        return font_name
    except Exception:
        return "Helvetica"


def build_styles(font_name: str) -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=sample["Title"],
            fontName=font_name,
            fontSize=20,
            leading=26,
            alignment=TA_CENTER,
            spaceAfter=18,
            textColor=colors.HexColor("#16324F"),
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=sample["Normal"],
            fontName=font_name,
            fontSize=11,
            leading=16,
            alignment=TA_CENTER,
            spaceAfter=8,
            textColor=colors.HexColor("#4F5D75"),
        ),
        "section": ParagraphStyle(
            "SectionHeading",
            parent=sample["Heading2"],
            fontName=font_name,
            fontSize=14,
            leading=20,
            spaceBefore=8,
            spaceAfter=8,
            textColor=colors.HexColor("#102A43"),
        ),
        "body": ParagraphStyle(
            "BodyTextCN",
            parent=sample["BodyText"],
            fontName=font_name,
            fontSize=10.5,
            leading=16,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "SmallTextCN",
            parent=sample["BodyText"],
            fontName=font_name,
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#52606D"),
        ),
    }


def make_image(path: Path, max_width: float, max_height: float) -> Image:
    image_reader = ImageReader(str(path))
    width, height = image_reader.getSize()
    ratio = min(max_width / width, max_height / height)
    return Image(str(path), width=width * ratio, height=height * ratio)


def build_table(data: list[list[object]], column_widths: list[float], font_name: str) -> Table:
    table = Table(data, colWidths=column_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9E2EC")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#102A43")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#9FB3C8")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FC")]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def draw_page_number(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#52606D"))
    canvas.drawRightString(PAGE_WIDTH - 1.8 * cm, 1.2 * cm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def generate_course_report(summary: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    font_name = register_fonts()
    styles = build_styles(font_name)

    dataset = summary["dataset"]
    split = summary["split"]
    ranking = summary["ranking"]
    results = summary["results"]
    best_model = summary["best_model"]
    artifacts = summary["artifacts"]

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="乳腺癌诊断二分类课程实验报告",
        author="OpenAI Codex",
    )

    best_result = results[best_model]
    story = [
        Paragraph("乳腺癌诊断二分类课程实验报告", styles["title"]),
        Paragraph("基于 scikit-learn 内置 Breast Cancer Wisconsin Diagnostic 数据集", styles["subtitle"]),
        Paragraph(
            "实验内容涵盖数据划分、标准化、传统模型对比、分类指标统计、混淆矩阵、ROC/AUC 分析以及自动化 PDF 报告生成。",
            styles["body"],
        ),
        Spacer(1, 0.2 * cm),
    ]

    story.append(Paragraph("一、实验目的", styles["section"]))
    story.append(
        Paragraph(
            "本实验以乳腺癌诊断任务为背景，构建一个可复现的二分类机器学习流程。"
            "目标是比较多种传统分类模型在相同训练/测试集与标准化条件下的表现，并形成规范化实验报告。",
            styles["body"],
        )
    )

    story.append(Paragraph("二、数据集与实验设置", styles["section"]))
    dataset_table = build_table(
        [
            ["项目", "内容"],
            ["数据集名称", dataset["dataset_name"]],
            ["数据来源", dataset["source"]],
            ["样本数", dataset["samples"]],
            ["特征数", dataset["features"]],
            ["标签定义", "0 = Benign, 1 = Malignant"],
            ["训练集 / 测试集", f"{split['train_samples']} / {split['test_samples']}"],
            ["随机种子", split["random_state"]],
            ["标准化方式", split["standardization"]],
        ],
        [4.2 * cm, 11.4 * cm],
        font_name,
    )
    story.append(dataset_table)
    story.append(Spacer(1, 0.2 * cm))
    story.append(
        Paragraph(
            f"数据集中共包含 {dataset['samples']} 个样本、{dataset['features']} 个数值特征。"
            f"其中良性样本 {dataset['class_distribution']['benign']} 个，恶性样本 {dataset['class_distribution']['malignant']} 个。"
            f"实验采用固定随机种子 {split['random_state']}，测试集比例为 {split['test_size']:.0%}。",
            styles["body"],
        )
    )

    story.append(Paragraph("三、模型与评价指标", styles["section"]))
    story.append(
        Paragraph(
            "实验比较 Logistic Regression、Support Vector Machine、K-Nearest Neighbors 与 Random Forest 四种传统模型。"
            "评价指标包括 Accuracy、Precision、Recall、F1-score、混淆矩阵以及 ROC/AUC。"
            "其中 Precision、Recall、F1-score 均以恶性样本（Malignant）作为正类进行计算。",
            styles["body"],
        )
    )

    story.append(Paragraph("四、结果对比", styles["section"]))
    metrics_table_data = [["Model", "Accuracy", "Precision", "Recall", "F1", "AUC"]]
    for row in ranking:
        metrics_table_data.append(
            [
                row["model"],
                f"{row['accuracy']:.4f}",
                f"{row['precision']:.4f}",
                f"{row['recall']:.4f}",
                f"{row['f1']:.4f}",
                f"{row['roc_auc']:.4f}",
            ]
        )
    story.append(
        build_table(
            metrics_table_data,
            [5.1 * cm, 2.1 * cm, 2.1 * cm, 2.1 * cm, 1.8 * cm, 1.8 * cm],
            font_name,
        )
    )
    story.append(Spacer(1, 0.25 * cm))
    story.append(
        Paragraph(
            f"按照 F1-score、AUC、Accuracy 的综合排序，本次实验表现最佳的模型为 {best_model}。"
            f"其测试集 Accuracy 为 {best_result['accuracy']:.4f}，Precision 为 {best_result['precision']:.4f}，"
            f"Recall 为 {best_result['recall']:.4f}，F1 为 {best_result['f1']:.4f}，AUC 为 {best_result['roc_auc']:.4f}。",
            styles["body"],
        )
    )

    story.append(
        make_image(
            Path(artifacts["metric_comparison"]),
            max_width=CONTENT_WIDTH,
            max_height=8.4 * cm,
        )
    )
    story.append(Spacer(1, 0.2 * cm))
    story.append(
        make_image(
            Path(artifacts["roc_curve"]),
            max_width=CONTENT_WIDTH,
            max_height=8.6 * cm,
        )
    )

    story.append(PageBreak())
    story.append(Paragraph("五、混淆矩阵分析", styles["section"]))
    story.append(
        Paragraph(
            "下图展示各模型在测试集上的混淆矩阵。主对角线越突出，说明模型正确分类的样本越多；"
            "对恶性样本的漏判数量越少，通常意味着模型在实际医学筛查场景中更具参考价值。",
            styles["body"],
        )
    )

    for model_name, result in results.items():
        story.append(Paragraph(model_name, styles["body"]))
        story.append(
            make_image(
                Path(result["artifacts"]["confusion_matrix_png"]),
                max_width=CONTENT_WIDTH,
                max_height=7.2 * cm,
            )
        )
        story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph("六、实验结论", styles["section"]))
    story.append(
        Paragraph(
            "1. 在相同的数据划分与标准化条件下，不同传统模型在该数据集上均取得了较高的分类性能，"
            "说明 Breast Cancer Wisconsin Diagnostic 数据集具有较好的可分性。",
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            f"2. {best_model} 在本次实验中的综合指标最优，尤其在恶性样本识别方面取得了较平衡的 Precision 与 Recall，"
            "因此更适合作为本次课程实验的推荐模型。",
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            "3. 自动化实验脚本能够一键完成训练、评估、绘图和 PDF 报告生成，适合用于课程提交、结果复现与后续扩展。",
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            "附注：图表、指标表与 PDF 均由程序自动落盘，便于在课程作业中直接引用。",
            styles["small"],
        )
    )

    doc.build(story, onFirstPage=draw_page_number, onLaterPages=draw_page_number)
