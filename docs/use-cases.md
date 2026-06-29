# MailGuard-AI — Use cases

The system supports three personas:

| Persona | Description |
|---------|-------------|
| **End user** | Reads emails in Gmail, gets inline classification + can submit feedback. |
| **Power user** | End user + manages their whitelist/blacklist, reviews predictions. |
| **Admin** | Manages model versions (register, activate, roll back). |

## UC-01 · Classify an email

| Field | Description |
|-------|-------------|
| Actor | End user (via Chrome extension) |
| Pre-condition | The extension is installed + the user is logged in. |
| Trigger | The user opens an email in Gmail. |
| Main flow | 1. Gmail scraper extracts (sender, subject, body, links). 2. Extension sends `POST /api/v1/predictions`. 3. Backend persists the `Email` row. 4. Backend calls AI Service `POST /predict`. 5. Backend persists the `Prediction`. 6. Backend returns the prediction. 7. Extension renders the banner + highlights spans. |
| Post-condition | User sees the verdict inline; a `Prediction` row exists; an `ActivityLog` records the request. |
| Exceptions | Network error → toast. Auth expired → redirect to popup login. AI unreachable → fallback banner ("unavailable"). |

## UC-02 · Submit feedback

| Field | Description |
|-------|-------------|
| Actor | End user |
| Pre-condition | A prediction exists. |
| Trigger | User clicks "✅ Mark correct" or "❌ Report mistake" on the banner. |
| Main flow | Extension sends `POST /api/v1/feedback`. Backend persists `Feedback` row + activity log. |
| Post-condition | The feedback is stored for future retraining. |
| Exceptions | Prediction not found (rare, race condition) → 404 toast. |

## UC-03 · Manage whitelist / blacklist

| Field | Description |
|-------|-------------|
| Actor | Power user |
| Pre-condition | User is logged in. |
| Trigger | User opens the Options page (or "Manage lists" in the popup). |
| Main flow | User enters sender + note/reason. Backend validates, persists a row, and returns the list. List is re-rendered. |
| Post-condition | Future classifications can short-circuit on these lists. |

## UC-04 · View dashboard

| Field | Description |
|-------|-------------|
| Actor | Power user |
| Pre-condition | User is logged in and has at least one prediction. |
| Trigger | User opens `/dashboard.html`. |
| Main flow | Frontend calls `/dashboard/stats`, `/dashboard/recent`, `/dashboard/ai/health` and renders stats, class doughnut chart, threat-level bar chart, recent predictions table, and AI health. |
| Post-condition | User understands their threat landscape. |

## UC-05 · Publish a new model version

| Field | Description |
|-------|-------------|
| Actor | Admin |
| Pre-condition | An ML engineer has trained and saved a model artifact (e.g. `models/artifacts/baseline_naive_bayes.pkl`). |
| Trigger | Admin runs `train_baseline --evaluate --publish --activate` (or the equivalent `publish_model.py`). |
| Main flow | 1. Trainer uploads artifact to AI Service. 2. Evaluation runs on hold-out set; report is written to `datasets/eval_report/`. 3. `publish_model.py` calls `POST /api/v1/admin/models` (and `--activate` calls `/activate`). 4. Backend deactivates the previous active version + activates the new one. 5. AI Service now serves the new artifact. |
| Post-condition | New active model version is recorded. |

## UC-06 · Roll back a model

| Field | Description |
|-------|-------------|
| Actor | Admin |
| Pre-condition | At least 2 model versions exist. |
| Trigger | Admin clicks "Activate" on an older version row in `/admin.html`. |
| Main flow | Frontend calls `POST /admin/models/{id}/activate`. Backend toggles `is_active`. AI Service picks it up on next request. |
| Post-condition | Older model is active again. |

## UC-07 · A/B test two models

| Field | Description |
|-------|-------------|
| Actor | ML engineer / Admin |
| Pre-condition | Two model versions are registered. |
| Trigger | Operator sets `AB_TEST_ENABLED=true` and `AB_TEST_CHALLENGER=v1.1.0` on the AI Service. |
| Main flow | Each request is routed A or B with the configured weight. Responses carry `ab_bucket`. Backend stores predictions normally; feedback joined later can compute per-bucket accuracy. |
| Post-condition | Real-world A/B comparison; rollback is just a config flip. |

## UC-08 · Train with augmented data

| Field | Description |
|-------|-------------|
| Actor | ML engineer |
| Pre-condition | Training script + merged dataset ready. |
| Trigger | User adds `--augment` to `train_baseline` or `train_distilbert`. |
| Main flow | Trainer runs `augment_dataset()` which generates 4× strategy variants per minority row. New rows are added; trainer fits on the enlarged dataset. |
| Post-condition | Model is more robust to minority classes (`scam`, `spam`). |