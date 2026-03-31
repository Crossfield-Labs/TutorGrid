# Breast Cancer ML Lab Summary

Generated at: 2026-03-31 17:02:36

## Dataset
- Name: Breast Cancer Wisconsin Diagnostic
- Samples: 569
- Features: 30
- Positive class: Malignant
- Negative class: Benign

## Best Model
- Model: Logistic Regression
- Accuracy: 0.9737
- Precision: 0.9756
- Recall: 0.9524
- F1: 0.9639
- AUC: 0.9960

## Key Findings
- Best overall model: Logistic Regression, with accuracy=0.9737, precision=0.9756, recall=0.9524, f1=0.9639, auc=0.9960.
- Compared with the runner-up SVM (RBF Kernel), the best model improves F1 score by 0.0009.
- The data split is stratified and feature scaling is applied within the training pipeline, preventing test-set leakage.