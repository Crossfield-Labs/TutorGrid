# Breast Cancer Wisconsin Diagnostic 二分类课程实验

本项目使用 `scikit-learn` 自带的 `load_breast_cancer()` 数据集，完成一个可直接运行、可复现的传统机器学习二分类课程实验。

实验内容包括：

- 固定随机种子的训练集 / 测试集划分
- `StandardScaler` 标准化
- 4 个传统模型对比：Logistic Regression、SVM、KNN、Random Forest
- 自动计算并保存 Accuracy、Precision、Recall、F1、混淆矩阵、ROC/AUC
- 自动生成图表文件与课程风格 PDF 实验报告

## 运行方式

```bash
python main.py
```

可选参数：

```bash
python main.py --output-dir output --random-state 42 --test-size 0.2
```

## 依赖安装

```bash
pip install -r requirements.txt
```

## 输出结构

运行后会自动生成：

- `output/data/model_metrics.csv`
- `output/data/model_metrics.json`
- `output/data/experiment_summary.json`
- `output/figures/metric_comparison.png`
- `output/figures/roc_curves.png`
- `output/figures/confusion_matrix_*.png`
- `output/pdf/breast_cancer_course_report.pdf`

## 实验约定

- 仅使用 `scikit-learn` 内置数据集 `load_breast_cancer()`
- 固定随机种子，保证结果可复现
- 将恶性样本 `Malignant` 定义为正类，用于计算 Precision / Recall / F1 / ROC-AUC
