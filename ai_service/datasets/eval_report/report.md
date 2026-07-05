# Model Evaluation Report

- Total samples: **2000**
- Accuracy: **0.5035**
- Macro F1: **0.3172**  · Weighted F1: **0.6154**

## Per-class metrics

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| `normal` | 0.8742 | 0.5420 | 0.6691 | 1834 |
| `notification` | 0.0000 | 0.0000 | 0.0000 | 153 |
| `scam` | 0.1646 | 1.0000 | 0.2826 | 13 |

## Confusion matrix

| true \ pred | normal | notification | scam |
|---|---|---|---|
| `normal` | 994 | 98 | 65 |
| `notification` | 143 | 0 | 1 |
| `scam` | 0 | 0 | 13 |
