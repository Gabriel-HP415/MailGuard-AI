# MailGuard-AI — Nginx reverse proxy (optional, for production)

This is a production-ready nginx config that fronts all three services
behind a single domain with HTTPS via certbot.

## Layout

- `nginx.conf` — base nginx settings (worker processes, gzip, log format)
- `conf.d/mailguard.conf` — virtual host + reverse proxy rules
- `conf.d/ssl.conf` — TLS settings, certificate paths

## Usage

1. Update `conf.d/mailguard.conf` and replace `mailguard.example.com` with
   your real domain.
2. Provision TLS with `certbot --nginx -d mailguard.example.com`.
3. Mount the `conf.d/` directory into `/etc/nginx/conf.d/` inside the
   official `nginx:1.27-alpine` image, or use the included
   `Dockerfile.nginx-proxy`.

## Routes

| Domain | Forwards to |
|--------|-------------|
| `/`     | frontend (port 80 of `frontend`) |
| `/api/v1/*` | backend (port 8000 of `backend`) |
| `/ai/*`  | ai_service (port 8000 of `ai_service`) |