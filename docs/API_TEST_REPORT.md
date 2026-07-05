# API Test Report — 2026-07-05

## Environment

| Item | Value |
|---|---|
| Backend URL | http://127.0.0.1:8003 (host) / http://localhost:8000 (container) |
| Compose file | docker-compose.dev.yml |
| DB | PostgreSQL 16 (port 5433 host, 5432 container) |
| AI provider | stub (no external model required) |
| Firebase | disabled in dev mode |
| Python | 3.11.11 |
| FastAPI | 0.115 |

## Summary

| Metric | Count |
|---|---|
| Endpoints tested | **25** |
| Passed | **25** |
| Failed | **0** |
| Skipped | 0 |

## Smoke test script

Run:
```
docker compose -f docker-compose.dev.yml exec -e MG_BASE_URL=http://localhost:8000 backend python /tmp/smoke_test.py
```

## Results

### Public

| Method | Endpoint | Status | Detail |
|---|---|---|---|
| GET | `/api/v1/health` | 200 | `{"status":"ok"}` |
| GET | `/docs` | 200 | Swagger UI served |

### Auth

| Method | Endpoint | Status | Detail |
|---|---|---|---|
| POST | `/api/v1/auth/register` | 201 | `access_token` returned |
| POST | `/api/v1/auth/login` | 200 | `access_token` returned |
| GET  | `/api/v1/auth/me` | 200 | returns created user |
| POST | `/api/v1/auth/login` (wrong pw) | 401 | "Invalid credentials" |
| GET  | `/api/v1/auth/me` (anonymous) | 401 | "Not authenticated" |
| POST | `/api/v1/auth/login` (admin) | 200 | admin token issued |

### Predictions

| Method | Endpoint | Status | Detail |
|---|---|---|---|
| POST | `/api/v1/predictions` | 201 | stub classifier returns `predicted_class=normal` for sample email |
| GET  | `/api/v1/predictions` | 200 | paginated list |
| GET  | `/api/v1/predictions/{id}` | 200 | detail view |

### Emails

| Method | Endpoint | Status | Detail |
|---|---|---|---|
| POST | `/api/v1/emails` | 201 | persists Email row |
| GET  | `/api/v1/emails` | 200 | list, returns 2 items after smoke test |

### Whitelist & Blacklist

| Method | Endpoint | Status | Detail |
|---|---|---|---|
| POST | `/api/v1/lists/whitelist` | 201 | id=5 (auto-increment from prior tests) |
| GET  | `/api/v1/lists/whitelist` | 200 | 1 item |
| POST | `/api/v1/lists/blacklist` | 201 | id=5 |
| GET  | `/api/v1/lists/blacklist` | 200 | 1 item |
| DELETE | `/api/v1/lists/whitelist/{id}` | 204 | success |

### Feedback

| Method | Endpoint | Status | Detail |
|---|---|---|---|
| POST | `/api/v1/feedback` | 201 | linked to prediction |
| GET  | `/api/v1/feedback` | 200 | 1 item |

### Dashboard

| Method | Endpoint | Status | Detail |
|---|---|---|---|
| GET | `/api/v1/dashboard/stats` | 200 | keys: total, by_class, by_threat, avg_risk |
| GET | `/api/v1/dashboard/recent` | 200 | serialised list of recent predictions |
| GET | `/api/v1/dashboard/ai/health` | 200 | `{"status":"unreachable"}` (no AI service running) |

### Admin (RBAC)

| Method | Endpoint | As USER | As ADMIN |
|---|---|---|---|
| GET | `/api/v1/admin/models` | 403 (forbidden) ✅ | 200 (1 item) |

## Bugs fixed during this test cycle

1. **`user_role` enum casing**
   The original 0001 migration created `user_role` as `'USER', 'ADMIN'` (uppercase),
   but the SQLAlchemy model wraps the Python `UserRole` enum which has lowercase
   values `'user'/'admin'`. Without `values_callable`, SQLAlchemy would insert
   `'admin'` (lowercase) → rejected by Postgres. Added migration `0003_lowercase_user_role`
   that recreates `user_role` with lowercase values and backfills rows. Also added
   `values_callable=lambda enum: [e.value for e in enum]` to every `SAEnum(...)`
   so all enum values match across layers.

2. **`AI_PROVIDER=stub` was silently dropped**
   `ai_client.predict` only knew about `gemini`, `http`, and `local`. With
   `AI_PROVIDER=stub` set in the dev compose, requests fell through to the legacy
   HTTP path → 500 ("AI service unreachable"). Added an explicit stub branch with
   a deterministic rule-based classifier so the API works offline.

3. **`dashboard/recent` 500 on serialisation**
   Returned `Prediction` ORM objects directly, which broke FastAPI's JSON encoder
   on `DECIMAL` and `Enum` columns. Rewrote to serialise each prediction to a
   plain dict.

## Files changed

```
M  backend/alembic/versions/0003_lowercase_user_role.py   (new)
M  backend/app/api/v1/dashboard.py
M  backend/app/models/feedback.py
M  backend/app/models/prediction.py
M  backend/app/models/user.py
M  backend/app/services/ai_client.py
A  scripts/smoke_test.py
M  docker-compose.dev.yml                (CORS + 8003 added)
M  chrome_extension/manifest.json        (port 8003 whitelisted, version bump)
M  chrome_extension/scripts/test_extension_wiring.py  (new)
A  docs/EXTENSION_DEV_SETUP.md           (new)
A  docs/API_TEST_REPORT.md               (this file)
```

Commit: `7f740a4 fix(backend): align SQLAlchemy enums with Python str-Enum values + stub AI + dashboard serialize`

## Wiring probe (extension → dev backend)

Simulated the extension's first-run flow (`chrome.storage.local` lookup →
fall back to default → fetch /health). Result:

| Base URL | Status | env |
|---|---|---|
| `https://mailguard-ai-y0nh.onrender.com/api/v1` (prod default) | 200 | production |
| `http://localhost:8000/api/v1` (in-container) | 200 | development |
| `http://127.0.0.1:8003/api/v1` (from host Windows) | 200 | development |

All three reachable. Production URL is the extension's hardcoded default, so
when users first install they hit prod. To point at dev, set `mg_base_url` in
`chrome.storage.local` per `docs/EXTENSION_DEV_SETUP.md`.

## Recommendations / follow-ups

| Priority | Item | Owner |
|---|---|---|
| P1 | Replace stub classifier with real baseline model (Task T2.M2.1 in docs/TASKS.md) | M2 |
| P1 | Bring `/dashboard/ai/health` to "ok" by deploying AI service in dev (`docker compose --profile ai up`) | M2 / M5 |
| P2 | Convert smoke_test into proper pytest cases under `backend/tests/test_api_smoke.py` | M1 |
| P2 | Auto-load `chromium_id` from manifest and wire to dev backend in `CORS_ORIGINS` (env from `manifest.json`) | M5 |
| P3 | Wire GitHub Actions to run smoke_test on every push to `develop` | M5 |
