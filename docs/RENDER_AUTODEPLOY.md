# Auto-deploy từ GitHub lên Render

Một lần setup, sau đó mỗi lần `git push origin main` thì Render tự rebuild & redeploy.

## Bước 1: Render Dashboard

1. Vào https://dashboard.render.com/
2. Click vào service `mailguard-ai` (đã có sẵn từ `render.yaml`)
3. Vào tab **Settings** → kéo xuống **Auto-Deploy**
4. Đảm bảo:
   - Auto-Deploy: **Yes**
   - Branch: **`main`**
   - Source: **`GitHub`**

Nếu chưa connect GitHub, click **Connect GitHub** → Authorize → chọn repo `Gabriel-HP415/MailGuard-AI`.

## Bước 2: Test auto-deploy

```bash
# Tạo nhánh test thử
git checkout -b test/autodeploy
echo "" >> README.md
git commit -am "test: trigger auto-deploy"
git push origin test/autodeploy

# Mở PR trên GitHub, merge vào main
# Sau ~2-3 phút, vào Render Dashboard → Logs sẽ thấy build mới
```

## Bước 3: Verify

Sau khi push, vào https://mailguard-ai-y0nh.onrender.com/api/v1/health:
```json
{"status":"healthy","version":"...","db":"ok"}
```

## Cơ chế

```
git push origin main
        │
        ▼
GitHub webhook đẩy event → Render API
        │
        ▼
Render pull code mới (./backend folder) → docker build → docker run
        │
        ▼
Service chuyển sang "Deploying..." → "Live" (khoảng 90-180s)
        │
        ▼
Extension Chrome gọi vào api.mailguard-ai-y0nh.onrender.com → nhận bản mới
```

## Nếu deploy fail

Xem tab **Logs** trong Render Dashboard. Phổ biến nhất:
- `DATABASE_URL` empty → check tab **Environment**
- `JWT_SECRET_KEY` empty → generate `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- `GEMINI_API_KEY` invalid → lấy key mới từ https://aistudio.google.com/app/apikey