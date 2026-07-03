# Chạy MailGuard-AI Backend trên Local (không cần Docker / Render)

Hướng dẫn này dành cho việc dev/test extension trên Windows 11 mà không cần deploy Render hay chạy Docker.

## 1. Yêu cầu

- **Python 3.11.x** (KHÔNG dùng 3.12+ vì một số dep chưa có wheel cho Windows)
  - Tải từ https://www.python.org/downloads/release/python-31111/
  - Tick "Add Python 3.11 to PATH" khi cài
- **Git for Windows** (đã có)
- MySQL Server 8 (tùy chọn – có thể thay bằng SQLite cho dev)

## 2. Cài Python deps

```powershell
cd "D:\HOC TAP\doanAI\MailGuard-AI\backend"
py -3.11 -m pip install --upgrade pip
py -3.11 -m pip install -r requirements.txt
```

Nếu dùng SQLite (khuyến nghị cho dev nhanh), bỏ qua bước cài MySQL & chỉnh `DATABASE_URL` ở bước 3.

## 3. Tạo file .env

Copy `.env.example` sang `.env` rồi sửa các giá trị sau:

```env
APP_ENV=development
APP_DEBUG=true

# Nếu dùng MySQL local:
DB_HOST=localhost
DB_PORT=3306
DB_NAME=mailguard_ai
DB_USER=root
DB_PASSWORD=YOUR_MYSQL_PASSWORD

# Hoặc nếu dùng SQLite (không cần MySQL):
# DATABASE_URL=sqlite:///./mailguard.db

# JWT secret – dev thì đặt gì cũng được
JWT_SECRET_KEY=local-dev-secret-change-me

# Cho phép extension Chrome (popup) gọi từ máy bạn
CORS_ORIGINS=http://localhost:3000,http://localhost:5500,chrome-extension://*

# AI Service – nếu chạy local thì trỏ về đây
AI_PROVIDER=http
AI_SERVICE_URL=http://localhost:8001

# Tắt Firebase trên local (chỉ cần dev với email/password)
FIREBASE_ENABLED=false
```

## 4. Khởi động AI Service (cổng 8001)

Mở terminal #1:

```powershell
cd "D:\HOC TAP\doanAI\MailGuard-AI\ai_service"
py -3.11 -m pip install -r requirements.txt
py -3.11 -m uvicorn ai_service.app.main:app --reload --host 0.0.0.0 --port 8001
```

Lần đầu chạy sẽ tự động train baseline từ seed dataset (~10–30 giây).
Kiểm tra: mở http://localhost:8001/health — phải thấy `model_loaded: true`.

## 5. Khởi động Backend (cổng 8000)

Mở terminal #2:

```powershell
cd "D:\HOC TAP\doanAI\MailGuard-AI\backend"
py -3.11 -m alembic upgrade head
py -3.11 -m python -m app.database.seed
py -3.11 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Kiểm tra:
- http://localhost:8000/docs → Swagger UI
- http://localhost:8000/health → `{"status":"ok",...}`

## 6. Load extension vào Chrome

1. Mở `chrome://extensions/`
2. Bật **Developer mode**
3. **Load unpacked** → chọn thư mục:
   ```
   D:\HOC TAP\doanAI\MailGuard-AI\chrome_extension
   ```
4. Copy **Extension ID** (chuỗi 32 ký tự)

## 7. Trỏ extension về backend local

1. Click icon MailGuard → nút **Settings** / **Options**
2. Trong ô **Backend URL** nhập:
   ```
   http://localhost:8000/api/v1
   ```
3. Tab ra rồi quay lại (để trigger `change` event lưu)
4. Quay lại popup → **Register** để tạo tài khoản, hoặc **Sign in** nếu đã có tài khoản admin từ bước seed

## 8. Test trên Gmail

Mở https://mail.google.com → mở một email bất kỳ (có thể tự gửi cho mình email kiểu "Verify your account" để test).

Extension sẽ:
- Quét DOM trang Gmail
- Gọi `POST /api/v1/predictions` tới localhost:8000
- Backend gọi AI service localhost:8001
- Banner + highlight xuất hiện trong email

## 9. Khắc phục sự cố

| Lỗi | Cách xử lý |
|---|---|
| `pymysql.OperationalError: 1045 Access denied` | Sai `DB_PASSWORD` trong `.env` |
| `pymysql.OperationalError: 1049 Unknown database 'mailguard_ai'` | Chạy `mysql -u root -p -e "CREATE DATABASE mailguard_ai;"` |
| `Failed to fetch` trong popup | Backend chưa chạy, hoặc sai Base URL trong Options |
| `Can't load plugin: sqlalchemy.dialects:postgres` | URL Postgres bắt đầu bằng `postgres://` thay vì `postgresql://` – code đã tự normalize, nếu vẫn lỗi thì sửa thủ công trong `.env` |
| Banner không hiện | Gmail render sandbox; refresh trang (F5), mở đúng email |

## 10. Đổi từ local sang Render khi muốn deploy

Khi bạn sẵn sàng deploy, chỉ cần:
1. Vào Options page → đổi Backend URL sang `https://mailguard-ai-y0nh.onrender.com/api/v1`
2. Code không cần đổi gì

Backend local & Render dùng cùng schema → extension hoạt động giống nhau.
