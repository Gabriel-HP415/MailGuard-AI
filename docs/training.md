# Training the MailGuard-AI email classifier

This document walks through how to reproduce the current baseline NB
classifier from scratch. It targets the **3 required datasets** named in
the project proposal:

1. **Enron Email Dataset** — 2 sources combined:
   - `corbt/enron-emails` (HuggingFace parquet, ~165 MB shard).
   - `bvk/ENRON-spam` (HuggingFace CSV, Metsis subset).
2. **Phishing Email Dataset** (`zefang-liu/phishing-email-dataset`).
3. **Spam Classification Data** — currently we use the SMS Spam
   Collection mirrored in `codebasics/py` (5572 messages, all mapped to
   `notification` because SMS-length messages are short transactional
   notifications, not full emails). The Kaggle
   `abdallahwagih/spam-emails` dataset can be added via
   `merge_datasets.py` if you want a separate spam corpus.

## Quick start

From the repo root:

```powershell
# 1. (Optional) install just what we need for the baseline pipeline
python -m pip install pandas pyarrow pydantic pydantic-settings joblib

# 2. Build the merged dataset (downloads from HuggingFace + GitHub).
#    ~20 s on a typical laptop, ~500 MB disk for raw downloads.
python -m ai_service.scripts.merge_datasets

# 3. Train a Multinomial Naive Bayes baseline with class_weight="balanced".
#    ~12 minutes on 100 K samples. Saves to models/artifacts/.
python -m ai_service.scripts.train_baseline naive_bayes

# 4. Evaluate against a stratified 4 000-row sample of the merged dataset.
#    Writes Markdown + JSON under ai_service/datasets/eval_report/.
python -m ai_service.scripts.evaluate_baseline `
    --model ai_service/models/artifacts/baseline_naive_bayes.pkl `
    --max-samples 4000

# 5. Sanity-check predictions on a few hand-crafted emails.
python -m ai_service.scripts.smoke_test_baseline
```

The smoke test prints one line per email with the predicted class,
confidence, and full probability vector.

## What's inside the merged dataset

After `merge_datasets.py` finishes, `ai_service/datasets/merged_dataset.csv`
contains the columns `label, subject, body, source`:

| source               | label        | count    |
|----------------------|--------------|----------|
| `enron_corbt`        | normal       | 43 775   |
| `enron_spam_bvk`     | normal/ham   | 16 545   |
| `enron_spam_bvk`     | spam         | 17 171   |
| `phishing_kaggle`    | normal (safe)| see log  |
| `phishing_kaggle`    | scam         | ~7 000+  |
| `sms_spam_collection`| notification | 5 572    |

Total ≈ 100 K emails with the class distribution

```
normal          ~71 K
spam            ~17 K
scam            ~7 K
notification    ~5.5 K
```

## Current baseline metrics

```text
MultinomialNB | class_weight=balanced (via sample_weight in fit)
Eval: 4 000 stratified sample, 12 % hold-out = 12 K during fit
  accuracy           : 0.9493
  macro-F1           : 0.8822
  per-class F1       :
    normal           : 0.9932  (P=1.00, R=0.99)
    notification     : 0.9977  (P=1.00, R=1.00)
    spam             : 0.8674  (P=0.85, R=0.89)
    scam             : 0.6703  (P=0.67, R=0.67)
```

`spam` vs `scam` remain the hardest pair (marketing spam looks similar
to phishing-style scams to a bag-of-words model). Future iterations can
add dense character features + URL-domain features, or fine-tune a
DistilBERT classifier.

## How the parser handles tricky formats

Three quirks we had to deal with to actually reach the metrics above:

* **Enron parquet, not zip**: the `corbt/enron-emails` repo deleted the
  legacy `emails.csv.zip` after 2024. We now stream the first
  `train-00000-of-00003.parquet` shard.
* **Enron-spam wrapped in Python list literal**: every body is a quoted
  string like `'[Subject: ...\\nbody]'`. We strip the outer quotes,
  unescape `\n` via `unicode_escape`, and split subject off the body.
* **Phishing CSV column names**: actual header is
  `Unnamed: 0, "Email Text", "Email Type"`, not `label, text`. We sniff
  the header to find the text column, then route `"Phishing Email"`
  rows to `scam` and `"Safe Email"` rows to `normal`.

The CSV parser also raises `csv.field_size_limit` to 100 MB because
Phishing rows can have multi-MB bodies that exceed Python's default
131 KB.

## Files added / changed in this milestone

* `ai_service/scripts/merge_datasets.py` — URL updates, parquet reader,
  field-size limit raise, more robust Enron-spam + phishing parsers.
* `ai_service/app/models/baselines.py` — `class_weight` parameter,
  Logistic Regression algorithm, `compute_sample_weight` so NB/SVM
  benefit from balancing too. Pickle payload now round-trips.
* `ai_service/scripts/train_baseline.py` — multiplier bumped to 4x for
  the augment path.
* `ai_service/scripts/evaluate_baseline.py` (**new**) — pickle-aware
  evaluator that exercises `BaselineClassifier.predict` end-to-end and
  writes a Markdown + JSON report.
* `ai_service/scripts/smoke_test_baseline.py` (**new**) — 4 hand-written
  emails, one per class, for fast visual sanity checks during iteration.
* `ai_service/README.md` is unchanged; see also `docs/`.

## What's next (optional)

* Train DistilBERT for a transformer baseline (see
  `ai_service/scripts/train_distilbert.py`). Expect ~5–10 % accuracy
  gain on `scam` vs `spam` separation at the cost of a GPU + ~1 hour.
* Publish the trained artifact to the backend admin API:

  ```powershell
  python -m ai_service.scripts.train_baseline naive_bayes `
      --evaluate `
      --publish --version v1.0.0 `
      --admin-email admin@mailguard.ai --admin-password <your-pw> `
      --activate
  ```

* Wire the Chrome extension's content script
  (`chrome_extension/content/bootstrap.js`) to call `/predictions` via
  `chrome.runtime.sendMessage({type:"predict", payload:{...}})`. The
  service-worker `service-worker.classic.js` already handles this
  message.