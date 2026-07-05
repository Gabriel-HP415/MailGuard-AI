# MailGuard-AI — Chrome Extension Dev Setup

This page is the single source of truth for getting the extension talking
to your local dev backend. It assumes you followed `DEVELOPING.md` and
have `docker compose -f docker-compose.dev.yml up -d` running.

---

## TL;DR (90 giây)

```
1. Mở Chrome → chrome://extensions/
2. Bật "Developer mode" (toggle góc phải trên)
3. "Load unpacked" → chọn thư mục "chrome_extension/"
4. Click icon MailGuard trên thanh toolbar → popup hiện ra
5. Click "⚙ Open Settings" ở góc dưới popup
6. Trong Settings → "Backend URL" paste: http://127.0.0.1:8003/api/v1
7. Tài khoản seed: email = demo@localhost.dev, password = Demo1234!
8. Click "Sign in"
9. Đăng nhập Gmail thật → extension auto-scan inbox
```

---

## 0. Verify backend đang chạy

```powershell
curl http://127.0.0.1:8003/api/v1/health
```

Kết quả expect:
```
{"status":"ok","service":"MailGuard-AI","version":"1.0.0","env":"development"}
```

Nếu `Connection refused` → chạy `docker compose -f docker-compose.dev.yml up -d`.

---

## 1. Load extension trong Chrome

| Bước | Thao tác |
|---|---|
| 1.1 | Mở Chrome → thanh địa chỉ gõ `chrome://extensions/` |
| 1.2 | Toggle **Developer mode** ở góc phải trên |
| 1.3 | Click **Load unpacked** |
| 1.4 | Browse tới `d:\HOC TAP\doanAI\MailGuard-AI\chrome_extension\` |
| 1.5 | Click "Select Folder" |

Extension sẽ hiện trong danh sách với tên "MailGuard-AI". Nếu báo lỗi đỏ:

- "Manifest is not valid JSON" → check `manifest.json` đã được save
- "Could not load icon 'icons/icon16.png'" → ảnh chưa có, ignore warning

> **Tip:** để ý ID của extension (chuỗi 32 ký tự dưới tên extension).
> Copy ID này lại — sẽ cần nếu muốn dùng devtools console.

---

## 2. Cấu hình Backend URL

Có 3 cách:

### Cách A — Qua Options page (khuyến nghị)

1. Right-click icon MailGuard → **Options**
2. Hoặc vào `chrome://extensions/` → click "Details" của MailGuard →
   "Extension options"
3. Trong form "Account" → đổi **Backend URL** thành:
   ```
   http://127.0.0.1:8003/api/v1
   ```
4. Bấm **Sign in** với:
   - Email: `demo@localhost.dev`
   - Password: `Demo1234!`

### Cách B — Qua popup

1. Click icon MailGuard trên toolbar
2. Nếu popup hiện "Backend disconnected" → click "⚙ Open Settings"
3. Làm theo Cách A từ bước 3

### Cách C — DevTools console (cho debug)

```javascript
chrome.storage.local.set({
  mg_base_url: "http://127.0.0.1:8003/api/v1"
}, () => console.log("saved"));
```

Mở DevTools bằng cách:
1. `chrome://extensions/` → click "Service worker" (dưới MailGuard)
2. Console sẽ mở → paste câu lệnh trên

---

## 3. Verify kết nối

Trong popup MailGuard (sau khi sign in):

- "Status" pill phải hiện **green "Connected"**
- "Total scanned" phải > 0 (đếm từ lúc đăng nhập)
- Recent list hiện prediction mới nhất (sẽ trống nếu chưa scan Gmail)

Test nhanh bằng cách mở https://mail.google.com/ trong tab khác:

1. Service worker (background) sẽ chạy `chrome.alarms` mỗi 5 phút
2. Lần đầu: gọi `gmail.listInbox()` → có thể hiện OAuth popup (bước 4)

---

## 4. Gmail OAuth (chỉ lần đầu)

Extension sẽ tự động mở Google OAuth popup khi cần quyền đọc Gmail.
Anh cần Gmail test account riêng (không dùng email chính).

1. Tạo 1 Gmail mới (vd `test.mailguard@gmail.com`)
2. Gửi vài email test cho chính nó, bao gồm 1 email "phishing" giả lập
3. Mở Gmail, click icon MailGuard → click "Connect Gmail"
4. Google OAuth mở ra → chọn `test.mailguard@gmail.com`
5. Approve scope `gmail.readonly`

> **Nếu bị stuck ở "Verifying..."** → bị stuck là do `chrome.identity.getAuthToken`
> mà extension đang dùng. Workaround: dùng "Sign in with email/password" fallback trong popup
> (mở `<details>Advanced</details>` → "Sign in with Google" link).

---

## 5. Test các tính năng

### 5.1 Dự đoán email đơn lẻ

1. Mở popup → bấm "Scan sample email" (nếu có nút đó) hoặc chạy trong DevTools console của popup:
   ```javascript
   const api = await import(chrome.runtime.getURL("lib/api.js")).then(m => m.api);
   await api.loadConfig();
   const result = await api.predict({
     subject: "URGENT verify now",
     sender: "fake@phish.tk",
     body_text: "Click http://bit.ly/x to verify account, urgent!"
   });
   console.log(result);
   ```
2. Expect: `{predicted_class: "scam", risk_score: ~75, threat_level: "critical"}`

### 5.2 Whitelist / Blacklist

1. Options page → nhập `trusted@gmail.com` → "Add" (Whitelist)
2. Popup reload → vào "Lists" → hiện entry
3. Backend sẽ tự cache entry này cho user

### 5.3 Feedback

1. Trong popup → click "👍 Correct" hoặc "👎 Wrong" trên 1 prediction
2. POST `/api/v1/feedback` → status 201

---

## 6. Debug

### Xem log của extension

| Cách | Mở |
|---|---|
| Service worker log | `chrome://extensions/` → link "Service worker" |
| Popup log | Click icon MailGuard → F12 (DevTools mở riêng cho popup) |
| Options page log | Options → F12 |
| Content script log (Gmail) | Mở Gmail → F12 → Console |

### Kiểm tra storage state

```javascript
chrome.storage.local.get(null, (s) => console.log(s));
```

### Reset extension (nếu bị stuck)

1. `chrome://extensions/` → MailGuard → toggle OFF → ON
2. Hoặc click "Remove" → load lại unpacked

---

## 7. Switching giữa dev và prod

Sau khi đã sign in dev (token trong storage), muốn test prod:

1. Options page → đổi Backend URL → `https://mailguard-ai-y0nh.onrender.com/api/v1`
2. Logout
3. Login lại bằng tài khoản prod
4. Token + base URL persist trong `chrome.storage.local`

---

## 8. Các lỗi thường gặp

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| `Failed to fetch` khi sign in | Backend chưa chạy / sai port | Check `curl http://127.0.0.1:8003/api/v1/health` |
| `CORS policy` block | Backend không cho phép origin | Update `CORS_ORIGINS` env, restart backend |
| `401 Unauthorized` | Token hết hạn / sai | Sign out → Sign in lại |
| `500 AI service unreachable` | AI_PROVIDER không phải `stub` | Set `AI_PROVIDER=stub` trong `docker-compose.dev.yml` |
| Gmail OAuth stuck | Bug đã fix, nếu vẫn stuck | Dùng email/password fallback trong popup |
| `Could not load manifest` | Sai đường dẫn khi load | Browse đến folder `chrome_extension/`, không phải folder cha |

---

## 9. Tắt dev stack khi xong

```powershell
# Giữ data (DB), chỉ stop containers
docker compose -f docker-compose.dev.yml down

# Xoá luôn data
docker compose -f docker-compose.dev.yml down -v

# Khởi động lại
docker compose -f docker-compose.dev.yml up -d
```

---

## 10. Tham khảo nhanh

| Tài nguyên | Đường dẫn |
|---|---|
| Backend API live | http://127.0.0.1:8003/docs |
| Backend health | http://127.0.0.1:8003/api/v1/health |
| Adminer (DB UI) | http://localhost:8081 |
| Backend log realtime | `docker compose -f docker-compose.dev.yml logs -f backend` |
| Smoke test (CI) | `scripts/smoke_test.py` |
| Wiring probe | `scripts/test_extension_wiring.py` |
| Setup team (5 người) | `docs/TASKS.md` + `CONTRIBUTING.md` |
