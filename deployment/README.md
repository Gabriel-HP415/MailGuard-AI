# MailGuard-AI — Deployment

Production deployment artifacts for the full stack.

## Files

| File | Purpose |
|------|---------|
| `docker-compose.yml`       | 4-service stack: mysql, backend, ai_service, frontend |
| `.env.example`             | Environment template |
| `nginx/nginx.conf`         | Base nginx settings |
| `nginx/conf.d/mailguard.conf` | Reverse proxy (domain → services) |
| `nginx/README.md`          | How to wire up HTTPS via certbot |
| `Dockerfile.nginx-proxy`   | Optional: turn the nginx config into a container |

## Quickstart

```bash
# 1. Copy env template
cp deployment/.env.example deployment/.env
# edit JWT_SECRET_KEY, DB_PASSWORD, etc.

# 2. Build & start everything
docker compose -f deployment/docker-compose.yml --env-file deployment/.env up -d --build

# 3. Initialise database
docker compose -f deployment/docker-compose.yml exec backend \
    alembic upgrade head
docker compose -f deployment/docker-compose.yml exec backend \
    python -m app.database.seed

# 4. (Optional) train an initial model
docker compose -f deployment/docker-compose.yml exec ai_service \
    python -m ai_service.scripts.train_baseline naive_bayes --augment

# 5. Publish that model + activate
docker compose -f deployment/docker-compose.yml exec backend \
    python -m ai_service.scripts.publish_model \
        --version v1.0.0 \
        --algorithm naive_bayes \
        --accuracy 0.0 \
        --artifact-path /app/../models/artifacts/baseline_naive_bayes.pkl \
        --description "Initial release" \
        --admin-email admin@example.com --admin-password secret --activate
```

## Smoke test

```bash
python scripts/health_check.py --backend http://localhost:8000 --ai http://localhost:8001
```

## Production hardening

- Set `APP_ENV=production` and ensure `LOG_LEVEL=INFO`
- Rotate `JWT_SECRET_KEY` regularly
- Run `mysql` with TLS (`--ssl-mode=REQUIRED`) if external access
- Mount the reverse proxy and provision TLS via `certbot`
- Restrict CORS origins in `CORS_ORIGINS`