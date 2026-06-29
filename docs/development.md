# MailGuard-AI — Development guide

## Layout

```
MailGuard-AI/
├── backend/                 # FastAPI
│   ├── app/
│   │   ├── api/             # routers + errors + deps
│   │   ├── core/            # config, security, constants
│   │   ├── database/        # SQLAlchemy engine + seed
│   │   ├── middleware/
│   │   ├── models/          # ORM
│   │   ├── schemas/         # Pydantic
│   │   └── services/        # business logic
│   ├── alembic/             # migrations
│   └── tests/
├── ai_service/              # ML serving
│   ├── app/
│   │   ├── preprocessing/   # text + URL + augmentation
│   │   ├── models/          # baselines + distilbert + registry
│   │   ├── risk/            # 0-100 scoring
│   │   ├── xai/             # SHAP, highlighter, summary
│   │   ├── serving/         # A/B testing harness
│   │   ├── predictor.py
│   │   ├── main.py          # FastAPI
│   │   ├── config.py
│   │   └── schemas.py
│   ├── scripts/             # merge_datasets, train_*, evaluate, publish_model
│   └── tests/
├── chrome_extension/        # Manifest V3
│   ├── lib/                 # api.js + ui.js
│   ├── content/             # gmail-scraper + highlighter + bootstrap
│   ├── popup/               # toolbar popup
│   ├── options/             # full-page settings
│   ├── background/          # service worker
│   └── manifest.json
├── frontend/                # Bootstrap 5 dashboard
│   ├── assets/{css,js,vendor}
│   ├── partials/
│   └── *.html
├── deployment/              # docker-compose, nginx, env template
├── scripts/                 # build_extension.py, fetch_frontend_assets.py,
│                            #   health_check.py
└── docs/                    # this directory
```

## Running tests

```bash
# Backend
cd backend
pytest -q

# AI Service
cd ai_service
pytest -q

# Frontend: no automated tests (vanilla JS, manual QA)
```

## Linting

```bash
# Backend
ruff check backend/app backend/tests
black --check backend/app backend/tests
isort --check-only backend/app backend/tests

# AI Service
ruff check ai_service/app ai_service/tests ai_service/scripts
black --check ai_service
isort --check-only ai_service
```

## Adding a new endpoint

1. Add a Pydantic schema in `backend/app/schemas/`.
2. Add a service function in `backend/app/services/`.
3. Add a router file (or extend one) in `backend/app/api/v1/`.
4. Register the router in `backend/app/api/v1/router.py`.
5. Add a pytest test under `backend/tests/`.
6. Update the backend README table.

## Adding a new classifier

1. Implement a class with `fit(texts, labels)` and `predict(text)` in
   `ai_service/app/models/`.
2. Register it in `ai_service/app/models/registry.py` and
   `app/models/__init__.py`.
3. Add a training entry point under `ai_service/scripts/`.
4. Add a unit test in `ai_service/tests/`.
5. Publish the resulting version with
   `python -m ai_service.scripts.publish_model ... --activate`.

## Browser-side development

```bash
# 1. Make sure your backend is running on http://localhost:8000
# 2. Open chrome://extensions/, enable Developer mode
# 3. Click "Load unpacked" and pick the chrome_extension/ folder
# 4. Change files; click the ⟲ reload button on the extension card
```

## Frontend dashboard

```bash
python scripts/fetch_frontend_assets.py
python -m http.server 8080 --directory frontend
# open http://localhost:8080/
```