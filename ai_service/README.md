# MailGuard-AI — AI Service

The AI Service is a FastAPI micro-service that classifies emails as
`normal`, `notification`, `spam`, or `scam` and provides risk scoring +
explainability. It is consumed by the backend via HTTP.

## Folder layout

```
ai_service/
├── app/
│   ├── main.py                    # FastAPI app
│   ├── config.py                  # Settings
│   ├── constants.py               # Enums + keyword weights
│   ├── schemas.py                 # Pydantic input/output
│   ├── predictor.py               # End-to-end predict() pipeline
│   ├── preprocessing/             # Text cleaning + URL analysis
│   │   ├── text_cleaner.py
│   │   └── url_extractor.py
│   ├── models/                    # Classifiers
│   │   ├── baselines.py           # NB / SVM / RF + TF-IDF
│   │   ├── distilbert_classifier.py
│   │   ├── classifier.py          # Unified EmailClassifier
│   │   └── registry.py            # Singleton model loader
│   ├── risk/
│   │   └── scorer.py              # 0-100 risk score
│   └── xai/
│       ├── highlighter.py         # Span detection
│       └── summary.py             # Human-readable summary
├── scripts/
│   ├── merge_datasets.py          # Build unified CSV
│   ├── train_baseline.py
│   └── train_distilbert.py
├── datasets/
│   └── merged_dataset.csv         # Generated
├── models/
│   └── artifacts/                 # Saved models
├── tests/                         # Pytest
├── requirements.txt
├── Dockerfile
└── README.md
```

## Datasets

The training data is built by `ai_service/scripts/merge_datasets.py`, which
combines three well-known public corpora. The choices mirror the three
Kaggle notebooks the project started from:

| Source | Class(es) | Description |
|--------|-----------|-------------|
| `corbt/enron-emails` (Hugging Face) | `normal` | The full Enron email corpus (~500K raw RFC-822 messages). All rows are treated as `normal` (legitimate ham). |
| `bvk/ENRON-spam` (Hugging Face) | `spam` + `normal` | The Metsis et al. 2006 Enron subset (33,716 messages) with explicit `spam` / `ham` labels. Used to reinforce the `spam` class. |
| `zefang-liu/phishing-email-dataset` (Hugging Face) | `scam` + `normal` | A copy of the Kaggle "Phishing_Email.csv" (18,650 rows). `Phishing Email` → `scam`, `Safe Email` → `normal`. Subject and body are concatenated into the body column. |
| SMS Spam Collection (mirrored in `codebasics/py`) | `notification` | The classic 5,572-message UCI SMS Spam dataset. Per project decision, **all** rows are mapped to `notification` (SMS-style transactional messages). |

The merge is **resilient** — if any individual download fails, the
corresponding source is skipped (with a warning) and the rest of the merge
still completes. Synthetic normal / notification / spam / scam samples are
added as fallbacks so every class is always represented.

### Run

```bash
# 1. Install
pip install -r requirements.txt

# 2. Merge datasets (downloads all 3 corpora + adds synthetic fallbacks)
python -m ai_service.scripts.merge_datasets

# 2b. Optional: cap the number of samples per source to keep training fast
python -m ai_service.scripts.merge_datasets \
    --max-enron 50000 \
    --max-enron-spam 20000 \
    --max-phishing 20000 \
    --max-sms 5000

# 3. Train a baseline (fast, no GPU)
python -m ai_service.scripts.train_baseline naive_bayes

# 4. (Optional) Train DistilBERT
python -m ai_service.scripts.train_distilbert 3

# 5. Start the API
uvicorn ai_service.app.main:app --reload --port 8001
```

The merged dataset is written to `datasets/merged_dataset.csv` with the
columns `label, subject, body, source`.

## API

### POST /predict

```json
{
  "subject": "Verify your account now",
  "body": "Dear customer, click here to verify your account immediately: http://bit.ly/abc",
  "sender": "support@example.com",
  "links": ["http://bit.ly/abc"]
}
```

Response:
```json
{
  "predicted_class": "scam",
  "class_index": 3,
  "confidence": 0.93,
  "probabilities": {"normal": 0.02, "notification": 0.01, "spam": 0.04, "scam": 0.93},
  "risk_score": 87.5,
  "threat_level": "critical",
  "inference_time_ms": 42,
  "model_version": "distilbert-finetuned",
  "model_algorithm": "distilbert",
  "explanation": {"summary": "...", "components": {...}},
  "highlighted_spans": [...],
  "suspicious_urls": [...]
}
```

### POST /predict/batch

Classify many emails at once.

### GET /health

Health + active model version. Includes an `ab_test_enabled` flag when A/B
testing is configured.

## Training pipeline

```bash
# (Optional) Augment minority classes (scam, spam) during training
python -m ai_service.scripts.train_baseline naive_bayes --augment

# 4. (Optional) Train DistilBERT — also has --augment / --evaluate / --publish flags
python -m ai_service.scripts.train_distilbert 3 --augment

# Evaluate a model on the merged dataset
python -m ai_service.scripts.evaluate \
    --model models/artifacts/baseline_naive_bayes.pkl \
    --output-dir datasets/eval_report
```

After evaluation you can publish the model to the backend admin API:

```bash
# Login as admin → POST /admin/models (+ optional /activate)
python -m ai_service.scripts.publish_model \
    --version v1.0.0 \
    --algorithm naive_bayes \
    --accuracy 0.9741 \
    --artifact-path models/artifacts/baseline_naive_bayes.pkl \
    --description "Trained on merged_dataset.csv (augmented)" \
    --admin-email admin@example.com \
    --admin-password secret \
    --activate
```

Or do it all in one shot from the trainer:

```bash
python -m ai_service.scripts.train_baseline naive_bayes \
    --augment --evaluate --publish \
    --version v1.0.0 \
    --admin-email admin@example.com --admin-password secret --activate
```

## Data augmentation

`app/preprocessing/augment.py` augments the minority classes (`scam`, `spam`)
using four lightweight, dependency-free strategies:

| Strategy | What it does |
|----------|--------------|
| `synonym` | Swap words using a built-in phishing/spam synonym map. |
| `shuffle` | Pairwise reorder sentences to vary phrasing. |
| `url_noise` | Inject zero-width / NBSP characters in URLs. |
| `invisible` | Sprinkle adversarial invisible characters between words. |

Each original minority-class row spawns `multiplier` new variants
(configurable; default = 2).

## A/B testing

The AI Service can split inference traffic between the **active** model
(``A``) and a **challenger** model (``B``) to compare them in production
without a risky full rollout.

Configuration (env vars):

| Variable | Default | Meaning |
|----------|---------|---------|
| `AB_TEST_ENABLED` | `false` | Master switch |
| `AB_TEST_CHALLENGER` | (unset) | Version string of the challenger model (e.g. `v1.1.0`) |
| `AB_TEST_WEIGHT_B` | `0.2` | Probability of routing a request to B |

When enabled, each prediction response includes an `ab_bucket` field
(`"A"` or `"B"`) so the backend can later join it with feedback to compute
per-bucket accuracy / CTR.

## Risk scoring

Risk score (0-100) is the sum of:
- **Classification confidence** (0-70)
- **Suspicious keyword hits** (0-30)
- **URL risk analysis** (0-40)
- **Risky attachments** (0-15)

Mapped to `low` / `medium` / `high` / `critical` via the threshold table in
`app/risk/scorer.py`.

## Explainability

- **Highlighted spans** — exact start/end offsets in the body for suspicious
  keywords and risky URLs. The Chrome extension uses these to highlight
  dangerous text in the user's inbox.
- **Summary** — human-readable paragraph composed from the prediction +
  per-component risk contributions.
- **Top tokens (optional)** — when SHAP is installed, the service can
  produce token attributions. See `app/xai/`.