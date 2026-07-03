# Cấu hình Google OAuth cho MailGuard-AI

Extension cần quyền **đọc Gmail** thông qua Gmail API. Đây là hướng dẫn từng bước để setup OAuth client + thêm Gmail scopes vào project.

> ⏱️ Thời gian: ~30 phút (chưa tính thời gian Google review consent screen nếu publish ra ngoài).

---

## 1. Tạo Google Cloud Project (nếu chưa có)

1. Truy cập https://console.cloud.google.com/
2. Góc trên bên trái → **Select a project** → **New project**
3. Tên: `MailGuard-AI`
4. Bấm **Create**

---

## 2. Bật Gmail API

1. Vào **APIs & Services** → **Library**
2. Tìm `Gmail API` → bấm vào → **Enable**
3. (Optional) Bật thêm **People API** nếu muốn sync contacts

---

## 3. Configure OAuth Consent Screen

1. **APIs & Services** → **OAuth consent screen**
2. User type:
   - **External** (để user Gmail cá nhân đăng nhập được) ← chọn cái này
   - Internal (chỉ dùng cho Google Workspace)
3. Bấm **Create**

### App information

| Field | Giá trị gợi ý |
|---|---|
| App name | MailGuard-AI |
| User support email | email của bạn |
| App logo | (optional) upload logo extension |
| Application home page | https://github.com/your-org/mailguard-ai |
| Application privacy policy link | https://your-domain.com/privacy |
| Application terms of service link | https://your-domain.com/terms |
| Authorized domains | your-domain.com, render.com (nếu deploy Render) |
| Developer contact information | email của bạn |

### Scopes

Bấm **Add or remove scopes**, thêm các scope sau:

| Scope | Mục đích |
|---|---|
| `openid` | OpenID Connect |
| `email` | Lấy email user |
| `profile` | Lấy tên + avatar |
| `https://www.googleapis.com/auth/userinfo.email` | Verify email |
| `https://www.googleapis.com/auth/userinfo.profile` | Lấy profile |
| `https://www.googleapis.com/auth/gmail.readonly` | **Đọc Gmail** (quan trọng nhất) |
| `https://www.googleapis.com/auth/gmail.modify` | Tùy chọn: cho phép extension đánh label |

> ⚠️ Scope `gmail.readonly` chỉ cho phép **đọc**. Nếu muốn extension **tự động gắn nhãn** email scam vào folder "Spam" thì cần `gmail.modify`.

### Test users (chỉ khi app ở chế độ Testing)

Trong khi app chưa verify với Google, chỉ những email được thêm vào **Test users** mới đăng nhập được. Thêm email Gmail của bạn vào đây để test local.

---

## 4. Tạo OAuth 2.0 Client ID (Chrome Extension)

1. **APIs & Services** → **Credentials**
2. **Create credentials** → **OAuth client ID**
3. Application type: **Chrome extension** ← phải chọn đúng cái này
4. Name: `MailGuard-AI Chrome Extension`
5. Application ID: (xem bước tiếp)

### Lấy Extension ID

Trong Chrome:
1. Mở `chrome://extensions/`
2. Enable **Developer mode**
3. **Load unpacked** → chọn thư mục `chrome_extension/`
4. Copy **Extension ID** (chuỗi 32 ký tự, ví dụ: `dfmiohjepkicjcjdfakggiaikkohcfle`)

### Paste vào Google Cloud Console

Paste Extension ID vào ô **Application ID** → bấm **Create**.

Lưu lại **Client ID** dạng `XXXXXX-XXXX.apps.googleusercontent.com`.

---

## 5. Cập nhật manifest.json

Sửa file `chrome_extension/manifest.json`:

```jsonc
"oauth2": {
  "client_id": "PASTE_CLIENT_ID_HERE.apps.googleusercontent.com",
  "scopes": [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.readonly"
  ]
}
```

Sửa luôn cả `backend/app/core/config.py`:

```python
firebase_oauth_client_id: str = "PASTE_CLIENT_ID_HERE.apps.googleusercontent.com"
```

---

## 6. (Tùy chọn) Verify App với Google

Nếu muốn publish extension ra Chrome Web Store và user bất kỳ Gmail nào cũng dùng được:

1. **OAuth consent screen** → **Publish app**
2. Google sẽ yêu cầu:
   - Logo 120x120
   - Privacy policy URL (phải trỏ tới trang thật, không phải placeholder)
   - Terms of service URL
   - YouTube video demo (bắt buộc cho sensitive scopes như gmail.readonly)
   - Justification cho sensitive scopes
3. Submit → Google review ~2-4 tuần

Trong quá trình dev/test, **chỉ cần bước 1-5** (dùng test users).

---

## 7. Test OAuth flow

1. Mở `chrome://extensions/`
2. Click **Reload** trên extension MailGuard-AI
3. Click icon extension → popup hiện ra
4. Bấm **Connect Gmail**
5. Google OAuth screen hiện ra → chọn account Gmail
6. Screen consent hiện ra với các scope → bấm **Allow**
7. Popup chuyển sang dashboard với stats

Nếu gặp lỗi:

| Lỗi | Nguyên nhân | Cách fix |
|---|---|---|
| `redirect_uri_mismatch` | Application ID trong manifest không khớp với Google Cloud Console | Reload extension, copy đúng ID mới |
| `Access blocked: This app's request is invalid` | App chưa verify + email không trong test users | Thêm email vào OAuth consent screen > Test users |
| `invalid_client` | client_id sai | Paste lại đúng từ Google Cloud Console |
| `Gmail API 403` | Chưa enable Gmail API | Quay lại bước 2 |

---

## 8. Verify trong Gmail

Mở https://mail.google.com → mở một email bất kỳ.

Extension sẽ:
1. Tự động lấy Gmail access token
2. Scan inbox (cả 25 email mới nhất qua background watcher mỗi 5 phút)
3. Highlight email scam/nghi ngờ với banner màu đỏ/cam

---

## 9. Local Backend Connection

Trong extension **Options page**, đổi Backend URL thành:
- Local: `http://localhost:8000/api/v1`
- Render: `https://mailguard-ai-y0nh.onrender.com/api/v1`

Extension sẽ gọi:
- `POST /api/v1/auth/gmail/login` để verify Google token + cấp MailGuard JWT
- `POST /api/v1/predictions` để gửi email qua AI

---

## 10. Production checklist

- [ ] Đã enable Gmail API
- [ ] Đã configure OAuth consent screen (External)
- [ ] Đã tạo OAuth client (Chrome extension type)
- [ ] Extension ID đã paste đúng vào Google Cloud Console
- [ ] `manifest.json` chứa đúng client_id
- [ ] Test user đã được add (cho dev) hoặc app đã publish (cho production)
- [ ] Backend `.env` có `JWT_SECRET_KEY` mạnh
- [ ] CORS allow `chrome-extension://*`
- [ ] Privacy policy + ToS đã publish trên domain thật (không phải localhost)