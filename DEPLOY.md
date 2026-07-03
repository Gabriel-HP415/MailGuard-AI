# MailGuard-AI — Cloud Deployment Guide

Mục tiêu: đưa extension MailGuard-AI lên Chrome Web Store dạng "không cần Docker"
cho user cuối. Backend FastAPI deploy lên **Render** (free tier), database
**Supabase Postgres**, AI inference gọi thẳng **Google Gemini API**.

Sau khi deploy xong, bất kỳ ai cài extension đều dùng được — không cần backend
local.

---

## 1. Chuẩn bị 3 secrets (15 phút)

### 1.1 Gemini API key

1. Mở https://aistudio.google.com/app/apikey
2. **Create API key** → chọn (or create) GCP project
3. Copy key — dán tạm vào notepad. Chuỗi bắt đầu bằng `AIzaSy…`

### 1.2 Firebase service account JSON

1. Mở https://console.firebase.google.com → project `mailguard-ai-a7f0a`
2. ⚙️ **Project settings** → tab **Service Accounts**
3. **Generate new private key** → file `.json` tải về
4. Mở file bằng VS Code, copy **toàn bộ nội dung** (1 dòng duy nhất)

### 1.3 Supabase Postgres connection string

1. Mở https://supabase.com → **New project**
   - Name: `mailguard-ai`
   - Database password: đặt mạnh (lưu lại)
   - Region: gần bạn nhất
2. Đợi ~1 phút cho project khởi tạo
3. Vào **Settings** (biểu tượng bánh răng) → **Database**
4. Mục **Connection string** → tab **URI** → copy
   - Ví dụ: `postgres://postgres.xxxx:YOUR_PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres`
   - **Thay `YOUR_PASSWORD`** bằng password lúc tạo project
   - Nếu dùng **Session pooler** (port 6543) thì giữ nguyên, nếu **Direct** (port 5432) thì thay port

### 1.4 JWT secret (tự tạo)

Mở PowerShell:
```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
Copy output.

---

## 2. Push code lên GitHub

```powershell
cd "d:\HOC TAP\doanAI\MailGuard-AI"
git init
git add .
git commit -m "Add Gemini + Render deploy config"
git branch -M main
git remote add origin https://github.com/<your-username>/mailguard-ai.git
git push -u origin main
```

> Nếu chưa có GitHub repo, tạo nhanh tại https://github.com/new

---

## 3. Deploy backend lên Render (10 phút)

### 3.1 Tạo Blueprint

1. Mở https://dashboard.render.com
2. **New +** → **Blueprint**
3. Kết nối GitHub repo `mailguard-ai` vừa push
4. Render tự đọc `render.yaml` → thấy service `mailguard-ai`

### 3.2 Paste secrets

Khi Render hỏi, paste lần lượt:

| Env var | Giá trị |
|---------|---------|
| `DATABASE_URL` | Connection string từ Supabase |
| `JWT_SECRET_KEY` | Output từ `secrets.token_urlsafe` |
| `GEMINI_API_KEY` | Key `AIzaSy…` |
| `FIREBASE_CREDENTIALS_JSON` | Toàn bộ nội dung file `.json` (1 dòng) |

### 3.3 Deploy

Bấm **Apply** → Render build ~3-5 phút.

Khi xong, URL backend là:
```
https://mailguard-ai.onrender.com
```
(Có thể Render cho tên khác — copy đúng từ dashboard.)

### 3.4 Test backend

```powershell
curl https://mailguard-ai.onrender.com/health
```
Phải trả `{"status":"ok",...}`.

```powershell
curl https://mailguard-ai.onrender.com/api/v1/health
```
Cũng trả OK.

Nếu lỗi 500 → check **Logs** tab trên Render dashboard.

---

## 4. Khởi tạo database schema (1 phút)

Render free tier không có shell, nên chạy local một lần trỏ vào Supabase:

```powershell
cd "d:\HOC TAP\doanAI\MailGuard-AI\backend"
$env:DATABASE_URL = "postgres://postgres.xxxx:YOUR_PASSWORD@aws-0-xxxx.pooler.supabase.com:6543/postgres"
.\venv\Scripts\python.exe -m app.database.init_db
.\venv\Scripts\python.exe -m app.database.seed
```

Nếu không có `init_db` thì dùng Alembic:
```powershell
.\venv\Scripts\alembic.exe upgrade head
.\venv\Scripts\python.exe -m app.database.seed
```

---

## 5. Update extension default URL

Nếu Render cho URL khác `mailguard-ai.onrender.com`, sửa 3 file:

**`chrome_extension/lib/firebase-config.js`** (dòng 28):
```js
export const BACKEND_BASE_URL = "https://YOUR-ACTUAL-URL.onrender.com";
```

**`chrome_extension/lib/api.js`** (dòng 24):
```js
const DEFAULT_BASE_URL = "https://YOUR-ACTUAL-URL.onrender.com/api/v1";
```

**`chrome_extension/manifest.json`** → thêm dòng trong `host_permissions`:
```json
"https://YOUR-ACTUAL-URL.onrender.com/*",
```

---

## 6. Update OAuth redirect URI

1. Mở https://console.cloud.google.com → APIs & Services → Credentials
2. Click OAuth 2.0 Client ID `...co8nefc95oub7k7gvha196kjl8i7ia6e...`
3. **Authorized redirect URIs** đã có sẵn:
   ```
   https://dfmiohjepkicjcjdfakggiaikkohcfle.chromiumapp.org/oauth2
   ```
4. **Authorized JavaScript origins** thêm:
   ```
   https://YOUR-ACTUAL-URL.onrender.com
   ```

---

## 7. Test end-to-end

1. `chrome://extensions/` → 🔄 **Reload** MailGuard-AI
2. Click icon → **Options**
3. Kiểm tra Backend URL đúng Render URL
4. **Sign in with Google** → popup OAuth → chọn account
5. Mở Gmail → email mới tự động highlight phishing/spam (Gemini classify)

---

## 8. Submit lên Chrome Web Store (production)

1. Tạo tài khoản Chrome Web Store Developer ($5 một lần):
   https://chrome.google.com/webstore/devconsole
2. **Pack extension**:
   ```powershell
   cd "d:\HOC TAP\doanAI\MailGuard-AI\chrome_extension"
   # Xoá thư mục dev artifacts (nếu có)
   Compress-Archive -Path * -DestinationPath ..\mailguard-ai-extension.zip -Force
   ```
3. Upload zip + screenshots + description lên dashboard
4. Sau khi review (~3 ngày), URL public dạng:
   ```
   https://chrome.google.com/webstore/detail/mailguard-ai/xxxx
   ```

---

## Troubleshooting

| Lỗi | Nguyên nhân | Cách sửa |
|-----|-----------|---------|
| `pydantic-core metadata-generation-failed` | Render native Python runtime dùng 3.14, thiếu Rust toolchain | **Đã chuyển sang Dockerfile** (Python 3.11) — không còn lỗi này |
| `GEMINI_API_KEY is not set` | Chưa paste key vào Render | Render dashboard → Environment → edit |
| Backend 500 lúc startup | Firebase JSON sai format | Kiểm tra JSON là **1 dòng duy nhất**, không có newline |
| `connection refused` | DATABASE_URL sai | Test bằng psql trước khi deploy |
| Render "service unavailable" | Free tier đang sleep | Mở URL lần đầu — Render wake up sau ~30s |
| OAuth `redirect_uri_mismatch` | Extension ID đổi | Mỗi máy có extension ID khác nếu load unpacked — chỉnh trong OAuth client |

> **Lưu ý Docker:** Lần đầu build với Dockerfile sẽ mất ~5-7 phút (pull image
> `python:3.11.11-slim` + `pip install`). Sau đó cache lại → redeploy ~1-2 phút.

---

## Backend URLs hiện tại
- Production: `https://mailguard-ai-y0nh.onrender.com`
- Health check: `https://mailguard-ai-y0nh.onrender.com/api/v1/health`
- Default API base (chrome extension): `https://mailguard-ai-y0nh.onrender.com/api/v1`

---

## Chi phí

| Service | Free tier | Đủ cho |
|---------|-----------|--------|
| Render Web Service | 750 giờ/tháng | ~1 instance luôn chạy |
| Supabase Postgres | 500 MB, unlimited API | ~50k users |
| Gemini 1.5 Flash | 60 req/phút | ~1 user scan liên tục |
| Firebase Auth | Unlimited | Free |

Tổng: **$0/tháng** cho đến khi scale lớn.