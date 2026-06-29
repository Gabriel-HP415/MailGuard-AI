# MailGuard-AI

**MailGuard-AI** là tiện ích mở rộng Chrome sử dụng Trí tuệ nhân tạo, giúp phân tích email Gmail, phát hiện email lừa đảo (phishing, scam, spam) và giải thích lý do phân loại thông qua Explainable AI (XAI).

Hệ thống phân loại email thành 4 nhóm: **Bình thường – Thông báo – Spam – Lừa đảo/Phishing**.

> Đồ án cuối kỳ môn Trí tuệ nhân tạo.

---

##  Công nghệ sử dụng

| Thành phần | Công nghệ |
|------------|-----------|
| Chrome Extension | Manifest V3, JavaScript, Bootstrap 5 |
| Backend API | Python, FastAPI, SQLAlchemy |
| AI Service | scikit-learn, DistilBERT (Transformers), SHAP |
| Cơ sở dữ liệu | MySQL 8 |
| Dashboard | HTML/CSS, Bootstrap 5, Chart.js |
| Triển khai | Docker, docker-compose |
| Xác thực (Extension) | Firebase Authentication + Google OAuth (chrome.identity) |

---

##  Kiến trúc hệ thống

```
Chrome Extension  ──►  FastAPI Backend  ──►  AI Service (ML + XAI)
                                              │
                                              ▼
                                          MySQL Database
```

- **Chrome Extension**: đọc email Gmail, gửi nội dung lên Backend, hiển thị cảnh báo ngay trong Gmail.
- **Backend API**: xác thực người dùng (JWT nội bộ + Firebase ID token), nhận email, gọi AI Service, lưu lịch sử và phản hồi.
- **AI Service**: tiền xử lý văn bản, trích chọn đặc trưng, phân loại, giải thích và tính điểm rủi ro.
- **MySQL**: lưu người dùng, lịch sử dự đoán, phản hồi, whitelist/blacklist, phiên bản mô hình.
- **Firebase Authentication**: extension dùng `chrome.identity` để chạy OAuth Google, đổi `code` lấy Firebase ID token rồi gửi lên Backend (`POST /api/v1/auth/firebase/login`). Backend verify bằng `firebase-admin`, upsert user vào MySQL, cấp JWT nội bộ.

---

##  Cấu trúc dự án

```
MailGuard-AI/
├── chrome_extension/   # Tiện ích Chrome (Manifest V3)
├── backend/            # FastAPI server
├── ai_service/         # Mô hình AI (ML + DistilBERT + XAI)
├── frontend/           # Giao diện quản lý (Bootstrap 5 + Chart.js)
├── deployment/         # Docker Compose, nginx, .env example
├── scripts/            # Build scripts (extension zip, vendor assets, healthcheck)
└── docs/               # Tài liệu: architecture, ER, sequence, use cases, deployment
```

---

##  Phân loại email

| Mã | Nhãn | Mô tả |
|----|------|-------|
| 0 | Bình thường | Email trao đổi thông thường |
| 1 | Thông báo | Email thông báo tự động |
| 2 | Spam | Email quảng cáo, rác |
| 3 | Lừa đảo/Phishing | Email mạo danh, đánh cắp thông tin |

---

### Chạy bằng Docker

```bash
cd deployment
docker-compose up -d
```

### Chạy thủ công

```bash
# 1. Chạy mọi thứ qua Docker Compose (khuyến nghị)
docker compose -f deployment/docker-compose.yml --env-file deployment/.env up -d --build
docker compose -f deployment/docker-compose.yml exec backend alembic upgrade head
docker compose -f deployment/docker-compose.yml exec backend python -m app.database.seed

# 2. Hoặc chạy thủ công
# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000

# AI Service
cd ai_service
pip install -r requirements.txt
python -m ai_service.scripts.merge_datasets
python -m ai_service.scripts.train_baseline naive_bayes
uvicorn ai_service.app.main:app --reload --port 8001

# Dashboard
python scripts/fetch_frontend_assets.py
python -m http.server 8080 --directory frontend

# Extension: Chrome → chrome://extensions → Developer Mode → Load unpacked → chọn chrome_extension/
```

### Smoke test

```bash
python scripts/health_check.py
```

### Docs

| Document | Purpose |
|----------|---------|
| [`docs/architecture.md`](docs/architecture.md)         | High-level architecture + tech stack |
| [`docs/er-diagram.md`](docs/er-diagram.md)             | ER diagram, class taxonomy, threat levels |
| [`docs/use-cases.md`](docs/use-cases.md)               | Personas + numbered use cases |
| [`docs/sequence-diagrams.md`](docs/sequence-diagrams.md) | Mermaid sequence diagrams |
| [`docs/deployment.md`](docs/deployment.md)             | Docker compose deployment, scaling, security |
| [`docs/development.md`](docs/development.md)           | Repo layout, testing, adding endpoints |

---


