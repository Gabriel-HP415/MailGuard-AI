# Troubleshooting: Service Worker / Login Failures

## Triệu chứng thường gặp

### "Service worker registration failed. Status code: 3"

Chrome MV3 chỉ cho phép 1 file `service_worker` đơn lẻ trong manifest. Nếu file bị lỗi parse (ví dụ dùng `import` ES Module trong khi manifest thiếu `"type": "module"`), Chrome trả về `Status code: 3`.

**Fix đã áp dụng**: `manifest.json` đổi sang dùng `background/service-worker.classic.js` (non-module). File cũ `service-worker.js` (ES Module) vẫn còn trong repo nhưng **không được tham chiếu nữa** — nó chỉ dành cho Chrome >= 111 nếu sau này muốn bật lại.

### "Cannot use import statement outside a module" trong popup/options console

Nguyên nhân: Chrome cố chạy file `.js` qua classic script thay vì ES module.

Các file `.html` của extension **đã** đặt `<script type="module" src="...">` đúng:
- `popup/popup.html`
- `options/options.html`

Nếu vẫn thấy lỗi:
1. Mở `chrome://extensions/`
2. Click "Details" của MailGuard
3. Bật "Allow in incognito" + kiểm tra "Site access" cho phép `http://127.0.0.1:8003/*`
4. Click "Reload"
5. Nếu vẫn fail: mở DevTools cho Service Worker (link xanh "Service worker") xem log chi tiết

### Login popup báo "Failed to fetch" / CORS error

1. Verify backend đang chạy:
   ```powershell
   curl http://127.0.0.1:8003/api/v1/health
   ```
2. Trong Options page, đảm bảo Backend URL = `http://127.0.0.1:8003/api/v1`
3. Trong `chrome://extensions/`, kiểm tra extension có đủ host_permissions `http://127.0.0.1:8003/*`

### Login thành công nhưng popup vẫn "Offline"

1. Click icon MailGuard → F12 (DevTools cho popup)
2. Tab Console — gõ:
   ```javascript
   chrome.runtime.sendMessage({ type: "get-status" }, console.log);
   ```
3. Phải thấy `{ok: true, authenticated: true, base_url: "http://127.0.0.1:8003/api/v1"}`

### "Unknown message type" trong DevTools service worker

Popup/options đang gọi 1 message mà SW classic không handle. Hiện tại SW classic xử lý:
- `ping`, `login`, `register`, `logout`, `get-status`
- `set-base-url`, `predict`, `dashboard-stats`, `dashboard-recent`

Nếu popup cố gọi `gmail_login`, `firebase_signed_in`, v.v. → sẽ fail. Đây là **intentional** trong bản classic: các flow Gmail OAuth/Firebase phức tạp yêu cầu ES Module SW. Để test, dùng **email/password login** trước.

## Cách reset extension hoàn toàn

1. `chrome://extensions/` → MailGuard → "Remove"
2. Confirm xoá
3. Đợi 5 giây
4. "Load unpacked" lại từ `chrome_extension/`
5. Mở Service Worker DevTools → phải thấy log:
   ```
   [MailGuard-AI] extension installed (non-module SW)
   ```

## Kiểm tra Chrome version

`chrome://version/` → dòng "Google Chrome". Nếu < 111, SW classic **bắt buộc**.

## Test thủ công sau khi reload

```javascript
// Trong DevTools service worker console:
chrome.runtime.sendMessage({ type: "ping" }, (r) => console.log(r));
// Expect: {ok: true, base_url: "http://127.0.0.1:8003/api/v1"}

chrome.runtime.sendMessage({
  type: "login",
  payload: { email: "demo@localhost.dev", password: "Demo1234!" }
}, (r) => console.log(r));
// Expect: {ok: true, data: {access_token: "eyJ..."}}
```

Nếu cả hai đều OK → reload popup, login sẽ work.