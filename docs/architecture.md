# MailGuard-AI — Architecture

## High-level system diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                       Chrome Extension                            │
│  ┌───────────────┐  ┌────────────────┐  ┌──────────────────┐      │
│  │ Gmail Scraper │→ │ Highlighter    │→ │ Bootstrap JS     │      │
│  │  (DOM parse)  │  │ (banner + span)│  │ (predict + cache)│      │
│  └───────────────┘  └────────────────┘  └──────────────────┘      │
│         ▲                                                 │       │
│         │ DOM                                            │       │
│  ┌──────┴──────┐                                         ▼       │
│  │ mail.google │                              POST /api/v1/predict│
│  └─────────────┘                                         ▼       │
└──────────────────────────────────────────────────┬───────────────┘
                                                   │ HTTPS
                                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                       Backend API (FastAPI)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐    │
│  │  Auth (JWT)  │  │  Predictors  │  │  Whitelist/Blacklist │    │
│  │  + RateLimit │  │  + Feedback  │  │  + Dashboard stats   │    │
│  └──────────────┘  └──────────────┘  └──────────────────────┘    │
│         │              │                          │               │
│         ▼              ▼                          ▼               │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │               MySQL 8  (users, emails, predictions)      │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
                          │
                          │ JSON over HTTP
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                       AI Service (FastAPI)                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐    │
│  │  Preprocessing  │→ │  Classifier     │→ │  Risk + XAI    │    │
│  │ (clean, URL)    │  │ (baseline / DL) │  │ (score, spans) │    │
│  └─────────────────┘  └─────────────────┘  └────────────────┘    │
│                                                                  │
│  A/B testing: splits traffic A:active / B:challenger            │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                       Dashboard (Frontend)                        │
│  Bootstrap 5 + Chart.js, vanilla JS, hosted by nginx              │
│  Pages: login / dashboard / predictions / lists / admin           │
└──────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Chrome Extension (Manifest V3)

- **Gmail scraper**: parses DOM (`div.a3s`, `h2.hP`, `span[email]`, …)
  with multi-strategy fallbacks. Emits `mailguard:email-opened` events
  through a `MutationObserver`.
- **Highlighter**: injects a banner + marks suspicious spans (keywords +
  URLs) with tooltips.
- **API client** (`lib/api.js`): JSON over `fetch`, JWT in
  `chrome.storage.local`.
- **Background service worker**: handles login, registers tabs.

### 2. Backend (FastAPI)

- **Auth**: bcrypt + JWT (HS256).
- **Rate limit**: in-memory IP-keyed, 120 req/min default.
- **Endpoints**: `/auth`, `/emails`, `/predictions`, `/feedback`,
  `/lists/whitelist`, `/lists/blacklist`, `/dashboard/*`, `/admin/*`.
- **Errors**: standardized `{"error": {"code", "message", "details"}}`
  format via custom exception classes (`AppError`, `NotFoundError`, …).

### 3. AI Service

- **Preprocessing**: HTML strip + URL replace + email normalization.
- **Classifier**: pluggable (TF-IDF + NB/SVM/LR/RF baselines by default,
  DistilBERT for higher-quality).
- **Risk scoring**: weighted sum of class confidence + URL risk + keyword
  risk + attachments → 0–100.
- **Explainability**: highlighted spans, summary, optional SHAP tokens.
- **A/B testing**: switch traffic between active model and challenger via
  env config.

### 4. Database (MySQL 8)

- 8 tables: `users`, `emails`, `predictions`, `feedback`,
  `whitelist`, `blacklist`, `model_versions`, `activity_logs`.
- Migrations via Alembic.

### 5. Dashboard

- Static SPA: `index.html` redirects to login or dashboard based on the
  JWT in `localStorage`.
- Bootstrap 5 for layout + Chart.js for analytics.
- API calls go to the same `/api/v1/*` endpoints as the extension.

## Tech stack

| Layer | Tech |
|-------|------|
| Frontend (Chrome ext.) | Vanilla ES2017, chrome API, Mulberry CSS |
| Frontend (dashboard)  | Bootstrap 5, Chart.js, vanilla JS, nginx |
| Backend API           | FastAPI, SQLAlchemy 2.x, Pydantic v2, JWT (python-jose), bcrypt (passlib) |
| AI Service            | FastAPI, scikit-learn, Transformers (DistilBERT), SHAP (optional) |
| Database              | MySQL 8.0, Alembic |
| MLOps                 | Joblib artifact store, version registry, A/B test harness, evaluation reports |
| Orchestration         | Docker, docker compose, optional nginx reverse proxy |

## Data flow (1 request)

```
[User opens Gmail message]
        │
        ▼
[Gmail scraper extracts payload]
        │
        ▼
[POST /api/v1/predictions] ──▶ Backend
                                   │
                                   ▼
                            [Persist Email row]
                                   │
                                   ▼
                   [HTTP POST /predict → AI Service]
                                   │
                                   ▼
                       [AI Service classifies]
                                   │
                                   ▼
                       [Risk + XAI + Highlights]
                                   │
                                   ▼
              [Persist Prediction row] ──▶ Response
                                              │
                                              ▼
                                  [Highlighter renders banner]
```

## Non-functional concerns

- **Resilience**: per-dataset download fallback in the merge script;
  synthetic sample augmentation if a class ends up empty.
- **Privacy**: no email content leaves your infrastructure in production
  deployments (self-hosted).
- **Observability**: structured logs, request middleware, optional
  activity log table.
- **Scalability**: stateless API → horizontal scale behind a load balancer.
  AI Service is GPU-optional (falls back to DistilBERT-CPU).