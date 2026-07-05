# Developing — Quickstart 5 phút

Clone repo, chạy 1 lệnh, có backend + DB + UI.

## 0. Yêu cầu
- Docker Desktop 4.x+
- Git
- 4GB RAM trống

## 1. Lệnh duy nhất

```bash
git clone https://github.com/Gabriel-HP415/MailGuard-AI.git
cd MailGuard-AI
docker compose -f docker-compose.dev.yml up -d
# đợi ~30s cho Postgres + backend ready
docker compose -f docker-compose.dev.yml logs -f backend
```

Khi thấy `Uvicorn running on http://0.0.0.0:8000` → ấn `Ctrl+C` để thoát log.

## 2. Truy cập các service

| Service | URL | Credentials |
|---|---|---|
| Backend API | http://localhost:8000 | — (xem `/docs` cho Swagger UI) |
| API docs (Swagger) | http://localhost:8000/docs | — |
| Postgres UI (Adminer) | http://localhost:8081 | System: PostgreSQL, Server: postgres, User: mailguard, Pass: mailguard_dev, DB: mailguard_ai |
| Health check | http://localhost:8000/api/v1/health | — |
| AI service (opt-in) | http://localhost:8002 | `docker compose --profile ai -f docker-compose.dev.yml up` |

## 3. Tài khoản seed sẵn (chỉ trong dev)

| Role | Email | Password |
|---|---|---|
| Admin | admin@localhost.dev | Admin1234! |
| User demo | demo@localhost.dev | Demo1234! |

## 4. Test trong Chrome extension

1. Mở `chrome://extensions/`
2. Enable "Developer mode"
3. "Load unpacked" → chọn `chrome_extension/`
4. Right-click icon → "Options"
5. Đổi Backend URL → `http://localhost:8000/api/v1`
6. Mở Gmail, popup extension sẽ highlight email phishing

## 5. Chạy test

```bash
docker compose -f docker-compose.dev.yml exec backend pytest
```

## 6. Lint code

```bash
docker compose -f docker-compose.dev.yml exec backend ruff check app/
```

## 7. Reset toàn bộ

```bash
docker compose -f docker-compose.dev.yml down -v   # xoá DB + cache
docker compose -f docker-compose.dev.yml up -d
```

## 8. Các service phụ

| Command | Ý nghĩa |
|---|---|
| `docker compose -f docker-compose.dev.yml ps` | Xem container đang chạy |
| `docker compose -f docker-compose.dev.yml logs backend` | Xem log backend |
| `docker compose -f docker-compose.dev.yml exec backend bash` | Vào shell trong container backend |
| `docker compose -f docker-compose.dev.yml exec backend alembic revision --autogenerate -m "..."` | Tạo migration mới |
