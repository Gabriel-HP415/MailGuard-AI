# MailGuard-AI — Backend API

The backend is the main HTTP API. It is consumed by the Chrome Extension and the
Dashboard. It delegates ML work to the **AI Service** over HTTP.

## Endpoints (v1)

### Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Register a new user. |
| POST | `/api/v1/auth/login` | Exchange credentials for a JWT. |
| GET | `/api/v1/auth/me` | Current user info. |

### Emails

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/emails` | Submit a captured email for storage. |
| GET | `/api/v1/emails` | List emails of the current user. |
| GET | `/api/v1/emails/{id}` | Get a single email. |

### Predictions

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/predictions` | Classify an email via the AI Service. |
| GET | `/api/v1/predictions` | List predictions for the current user. |
| GET | `/api/v1/predictions/{id}` | Get a prediction with full explanation. |

### Feedback

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/feedback` | Submit Human-in-the-loop feedback. |
| GET | `/api/v1/feedback` | List own feedback. |

### Whitelist / Blacklist

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/lists/whitelist` | Add trusted sender. |
| GET | `/api/v1/lists/whitelist` | List trusted senders. |
| DELETE | `/api/v1/lists/whitelist/{id}` | Remove. |
| POST | `/api/v1/lists/blacklist` | Add suspicious sender. |
| GET | `/api/v1/lists/blacklist` | List suspicious senders. |
| DELETE | `/api/v1/lists/blacklist/{id}` | Remove. |

### Dashboard

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/dashboard/stats?days=30` | Aggregated statistics. |
| GET | `/api/v1/dashboard/recent?limit=10` | Recent predictions. |
| GET | `/api/v1/dashboard/ai/health` | AI service health. |

### Admin (role: admin)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/admin/models` | List model versions. |
| POST | `/api/v1/admin/models` | Register a new version. |
| PATCH | `/api/v1/admin/models/{id}` | Update (activate/deactivate). |
| POST | `/api/v1/admin/models/{id}/activate` | Activate a version. |

### System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health. |
| GET | `/docs` | Swagger UI. |
| GET | `/redoc` | ReDoc. |

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env       # then edit values
alembic upgrade head       # create tables
python -m app.database.seed
uvicorn app.main:app --reload --port 8000
```

## Docker

```bash
docker build -t mailguard-backend .
docker run --env-file .env -p 8000:8000 mailguard-backend
```

## Architecture notes

- **Auth**: bcrypt + JWT (HS256). Tokens default to 24h. Override via
  `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`.
- **Rate limiting**: in-memory, IP-keyed, 120 req/min default. Disable for
  the Chrome extension by IP-allowlisting in production.
- **Errors**: all errors are returned as `{"error": {"code", "message", "details"}}`
  — see `app/api/errors.py`.
- **AI service client**: HTTP with 30s default timeout, raises AppError
  on failure (maps to 5xx with descriptive body).

## Tests

```bash
pytest -q
```