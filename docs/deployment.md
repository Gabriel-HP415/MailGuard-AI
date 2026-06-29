# MailGuard-AI — Deployment guide

A complete walkthrough from "fresh machine" to "production".

## 1. Prerequisites

| Component | Version | Notes |
|-----------|---------|-------|
| Docker | 24+ | with compose v2 |
| Python  | 3.11 | only required for development / run scripts |
| MySQL   | 8.0 | can be the included container |
| Nginx   | 1.27 | optional, for production |

## 2. Quickstart (Docker Compose)

```bash
git clone https://github.com/your-org/MailGuard-AI.git
cd MailGuard-AI

# 1. Configure secrets
cp deployment/.env.example deployment/.env
$EDITOR deployment/.env       # edit JWT_SECRET_KEY, DB_PASSWORD, etc.

# 2. Build & launch
docker compose -f deployment/docker-compose.yml \
    --env-file deployment/.env up -d --build

# 3. Wait for healthchecks
docker compose -f deployment/docker-compose.yml ps

# 4. Initialise the database
docker compose -f deployment/docker-compose.yml exec backend alembic upgrade head
docker compose -f deployment/docker-compose.yml exec backend python -m app.database.seed

# 5. Train + publish an initial model
docker compose -f deployment/docker-compose.yml exec ai_service \
    python -m ai_service.scripts.train_baseline naive_bayes --augment

docker compose -f deployment/docker-compose.yml exec backend \
    python -m ai_service.scripts.publish_model \
        --version v1.0.0 --algorithm naive_bayes --accuracy 0.0 \
        --artifact-path /app/models/artifacts/baseline_naive_bayes.pkl \
        --description "Initial release" \
        --admin-email admin@example.com --admin-password secret --activate

# 6. Smoke test
python scripts/health_check.py
```

Open <http://localhost:8080> for the dashboard.

## 3. Production checklist

- [ ] `APP_ENV=production`
- [ ] `JWT_SECRET_KEY` is a 32+ char random string, kept secret.
- [ ] `DB_PASSWORD` is strong; root password is set.
- [ ] `CORS_ORIGINS` is set to the exact domain that serves the dashboard.
- [ ] TLS terminated by nginx (see `deployment/nginx/`).
- [ ] A backup strategy for the `mysql_data` volume.
- [ ] Reverse-proxy rate-limiting above 120 req/min if you have many users.
- [ ] Monitoring: Prometheus exporter or equivalent tailing the
  `/health` endpoints.
- [ ] Health check cron:
  `*/5 * * * * cd /srv/mailguard && python scripts/health_check.py`
- [ ] Log rotation: `docker compose logs` is fine for development; use
  a driver like Loki for prod.

## 4. Scaling

- **Backend**: stateless; scale horizontally behind nginx (`upstream backend
  { server backend1:8000; server backend2:8000; ... }`).
- **AI Service**: each replica loads the model in memory (~500 MB for
  DistilBERT). At scale, run multiple replicas and round-robin between them
  via nginx. Consider ONNX / quantization for smaller footprint.
- **MySQL**: vertical scale first; if you need > 1 M predictions / day,
  promote a read-replica for the dashboard.
- **Browser extension**: no server-side scaling needed.

## 5. Updating the model

```bash
# 1. Stop the old AI Service
docker compose -f deployment/docker-compose.yml stop ai_service

# 2. Train the new version on fresh data
docker compose -f deployment/docker-compose.yml run --rm ai_service \
    python -m ai_service.scripts.train_baseline distilbert --augment --evaluate

# 3. Publish & activate (rolls back the old one)
docker compose -f deployment/docker-compose.yml run --rm backend \
    python -m ai_service.scripts.publish_model \
        --version v1.1.0 --algorithm distilbert --accuracy 0.9742 \
        --artifact-path /app/models/artifacts/distilbert-v1.1.0 \
        --description "Retrained on Aug 2026 dataset" \
        --admin-email admin@example.com --admin-password secret --activate

# 4. Restart
docker compose -f deployment/docker-compose.yml start ai_service
```

Zero-downtime: keep the old container running, deploy the new one
side-by-side, swap traffic via DNS / nginx `upstream`, then retire the
old one.

## 6. Disaster recovery

- **MySQL volume loss**: `docker compose down -v` wipes data. Restore
  from nightly `mysqldump`. The included compose file does **not**
  automatically back up.
- **Bad model rollout**: `POST /api/v1/admin/models/{old_id}/activate`
  with the previous version.
- **Compromised JWT secret**: rotate and force-logout by setting
  `JWT_SECRET_KEY` to a new value (all tokens become invalid; users must
  re-login).

## 7. Observability

- `/health` on each service returns JSON for uptime + status.
- `ActivityLog` table records user-level events (login, predict,
  feedback, …).
- For metrics, add `prometheus-fastapi-instrumentator` to the backend &
  AI Service.

## 8. Security

- All API calls are over HTTPS in production (nginx enforces).
- Rate limit defaults to 120 req/min/IP. Tighten for public endpoints.
- Password storage: bcrypt (cost factor 12).
- No email body ever leaves your infrastructure in self-hosted
  deployments.
- The Chrome extension only has `activeTab` + `storage` + `scripting`
  permissions; it does **not** read `chrome.history` or bookmarks.