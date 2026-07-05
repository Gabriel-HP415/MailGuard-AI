# Contributing to MailGuard-AI

Chào các thành viên! Đây là workflow làm việc nhóm 5 người.

---

## 1. Quy tắc chung (đọc trước khi code)

- **Không push thẳng lên `main`.** Mọi thay đổi qua nhánh riêng + Pull Request.
- **Mỗi task 1 PR**, PR nhỏ (< 400 dòng diff) dễ review hơn.
- **Commit message** dạng Conventional Commits:
  - `feat:` — tính năng mới
  - `fix:` — sửa bug
  - `docs:` — chỉ markdown
  - `style:` — format, không đổi logic
  - `refactor:` — cấu trúc lại
  - `test:` — thêm/sửa test
  - `chore:` — build, CI, deps
- **Pull Request cần pass CI** (ruff + pytest) trước khi merge.

---

## 2. Setup lần đầu (15 phút)

### Yêu cầu
- Docker Desktop (đã có sẵn)
- Git
- (Optional) VSCode với extension "Remote - Containers"

### Bước 1 — Clone
```bash
git clone https://github.com/Gabriel-HP415/MailGuard-AI.git
cd MailGuard-AI
git checkout develop   # branch chính cho nhóm (sẽ tạo nếu chưa có)
```

### Bước 2 — Tạo nhánh riêng cho task bạn
```bash
git checkout -b feat/<tên-task>
# Ví dụ:
git checkout -b feat/m2-baseline-model
```

### Bước 3 — Khởi động dev stack
```bash
docker compose -f docker-compose.dev.yml up -d
```

Lệnh này sẽ:
- Tạo Postgres ở `localhost:5433`
- Build backend image với dev tools
- Chạy migrations + seed
- Bật uvicorn hot-reload ở `localhost:8000`

### Bước 4 — Verify
```bash
# Backend health
curl http://localhost:8000/api/v1/health

# Postgres UI (Adminer)
# Mở http://localhost:8081
#   System: PostgreSQL
#   Server: postgres   Port: 5432
#   User: mailguard   Password: mailguard_dev   DB: mailguard_ai

# Seed user (chỉ có trong dev)
#   email: demo@localhost.dev
#   password: Demo1234!
#   admin: admin@localhost.dev / Admin1234!
```

---

## 3. Workflow hàng ngày

```bash
# Sáng đến: pull code mới
git checkout develop && git pull

# Chuyển về nhánh task của bạn + merge develop vào
git checkout feat/<tên-task>
git merge develop     # resolve conflicts nếu có

# Code... (hot-reload tự động reload trong container)

# Test local
docker compose -f docker-compose.dev.yml exec backend pytest

# Commit + push
git add .
git commit -m "feat: add baseline TF-IDF model"
git push origin feat/<tên-task>

# Mở Pull Request trên GitHub: feat/<tên-task> → develop
```

---

## 4. Chia task cho 5 người

| ID | Member | Module | Branch prefix | File sở hữu |
|---|---|---|---|---|
| **M1** | Backend API | `backend/app/api/v1/` | `feat/m1-backend-*` | Thêm endpoint, schemas, services |
| **M2** | AI/ML | `ai_service/` | `feat/m2-ai-*` | Training, inference, model versioning |
| **M3** | Chrome Extension | `chrome_extension/` | `feat/m3-ext-*` | Popup, options, content scripts |
| **M4** | Frontend Web | `frontend/` | `feat/m4-web-*` | HTML/JS/CSS, responsive |
| **M5** | DevOps/Docs | `*.yml`, `docs/`, `.github/` | `feat/m5-deps-*` | CI, Dockerfile, README |

Chi tiết task xem file **`docs/TASKS.md`** (sẽ tạo dưới đây).

---

## 5. Khi bí / không chạy được

1. Đọc `docs/LOCAL_DEV.md` (nếu cài lỗi)
2. Đọc `docs/TROUBLESHOOTING.md`
3. Hỏi trong group chat, gửi kèm:
   - Output `docker compose -f docker-compose.dev.yml ps`
   - Log: `docker compose -f docker-compose.dev.yml logs backend | tail -100`
   - Branch + commit hash của bạn

---

## 6. Code review

- Review PR của người khác trong vòng 24h.
- Comment lịch sự, gợi ý thay vì chê.
- Approve chỉ khi bạn hiểu code + CI xanh.

---

## 7. Release

Mỗi cuối tuần nhóm trưởng merge `develop` → `main` (qua PR riêng), trigger Render auto-deploy.
