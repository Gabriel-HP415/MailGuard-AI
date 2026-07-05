# Baseline naive_bayes Evaluation
- Samples: 4000
- Accuracy: **0.9493**
- Macro F1: **0.8822**

## Per-class
| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| `normal` | 1.0000 | 0.9866 | 0.9932 | 2826 |
| `notification` | 0.9955 | 1.0000 | 0.9977 | 219 |
| `spam` | 0.8450 | 0.8910 | 0.8674 | 679 |
| `scam` | 0.6703 | 0.6703 | 0.6703 | 276 |

## Confusion matrix
| true \ pred | normal | notification | spam | scam |
|---|---|---|---|---|
| `normal` | 2788 | 1 | 20 | 17 |
| `notification` | 0 | 219 | 0 | 0 |
| `spam` | 0 | 0 | 605 | 74 |
| `scam` | 0 | 0 | 91 | 185 |