/**
 * MailGuard-AI — Tiny i18n module (VI / EN).
 *
 * Usage in popup:
 *   import { t, applyI18n, setLocale, getLocale } from "../lib/i18n.js";
 *   await setLocale("vi");
 *   applyI18n(document);   // swaps text via data-i18n="key"
 *
 * `t(key)` returns the string in the currently selected locale, falling back
 * to English, then to the key itself. Storage key: `mg_locale`.
 */

const STORAGE_KEY = "mg_locale";

const STRINGS = {
  en: {
    "header.online": "Online",
    "header.offline": "Offline",
    "header.backend_down": "Backend down",
    "header.ready": "Ready",
    "header.error": "Error",

    "status.backend_label": "Backend:",
    "status.test_btn": "Test",
    "status.testing": "Testing…",
    "status.test_ok": "✅ Backend is reachable at {url}",
    "status.test_fail": "❌ Cannot reach {url}. Is the docker container running?",
    "status.unreachable_hint":
      "⚠ Cannot reach {url}. Run `docker compose -f docker-compose.dev.yml up -d` and reload.",
    "status.sw_unreachable": "Cannot contact service worker: {msg}",

    "auth.heading": "Sign in",
    "auth.hint":
      "Use the email/password from your MailGuard-AI backend. Works on every Chrome version without needing Google OAuth.",
    "auth.email": "Email",
    "auth.password": "Password",
    "auth.signin": "Sign in",
    "auth.signout": "Sign out",
    "auth.register": "Register",
    "auth.signing_in": "Signing in…",
    "auth.registering": "Creating…",
    "auth.success": "Success — fetching dashboard…",
    "auth.required": "Email and password are required.",
    "auth.signed_out": "Signed out.",
    "auth.network_err": 'Cannot reach backend. Check "{url}" is running.',
    "auth.bad_credentials": "Wrong email or password (or this account doesn't exist).",
    "auth.validation_err": "Validation error: {msg}",
    "auth.rate_limited": "Too many sign-in attempts. Wait a minute and try again.",

    "auth.advanced_backend": "Need a different backend?",
    "auth.advanced_hint":
      "The URL above is read from <code>chrome.storage.local.mg_base_url</code>. Open Settings to change it, or run in DevTools console:",
    "auth.oauth_heading": "Sign in with Google (Gmail OAuth)",
    "auth.oauth_hint":
      "Requires Chrome Extension OAuth client configured in your Google Cloud project. The classic service worker doesn't route the Gmail flow yet — use email/password above for now.",
    "auth.oauth_btn": "Connect Gmail (coming soon)",

    "settings.link": "⚙ Settings",

    "dashboard.greeting": "Hello, {name}",
    "dashboard.wave": "👋",
    "dashboard.recent_title": "📊 Recent predictions",
    "dashboard.recent_hint": "(from server)",
    "dashboard.role_prefix": "Signed in as",

    "stat.predictions": "Predictions",
    "stat.risks": "Risks",
    "stat.avg_risk": "Avg risk",

    "empty.recent": "No predictions yet.",
    "empty.scan": "No scans yet.",

    "gmail.heading": "Gmail",
    "gmail.connected": "Gmail connected",
    "gmail.not_connected": "Not connected",
    "gmail.connect": "Connect Gmail",
    "gmail.connecting": "Connecting…",
    "gmail.disconnect": "Disconnect",
    "gmail.disconnecting": "Disconnecting…",
    "gmail.scan_now": "Scan inbox now",
    "gmail.scanning": "Scanning…",
    "gmail.scan_status_ok": "✅ Scanned {count} message{s}.",
    "gmail.last_scan_prefix": "Last scan: ",
    "gmail.connect_to_scan": "Connect Gmail to scan your inbox.",
    "gmail.scan_results_title": "📬 Gmail inbox scan results",
    "gmail.scan_results_hint": "(just scanned)",
    "gmail.mode_passive": "Mode: passive · batch {size}",
    "gmail.mode_active": "Mode: active (auto-scan every 5 min) · batch {size}",
    "gmail.mode_set": "Mode set to {mode}.",
    "gmail.active_toggle": "Active scanning (every 5 min)",
    "gmail.active_toggle_notify": "Notify on dangerous emails",
    "gmail.notif_block": "You can disable notifications in Chrome settings.",
    "gmail.notif_enabled_msg": "✅ You'll be notified when high-risk emails arrive.",
    "gmail.notify_threshold_label": "Notify threshold",

    "item.risk": "Risk",
    "item.error_pill": "error",
    "item.no_subject": "(no subject)",
    "item.explanation_btn": "Why?",
    "item.explanation_title": "AI explanation",
    "item.spans_heading": "Suspicious phrases",
    "item.urls_heading": "Suspicious links",
    "item.spans_empty": "No specific risky phrases flagged.",
    "item.urls_empty": "No suspicious links found.",
    "item.open_in_gmail": "Open in Gmail",

    "notification.danger_title": "⚠️ Email nguy hiểm!",
    "notification.danger_message":
      "Phát hiện email rủi ro cao từ {sender}: {subject}",
  },

  vi: {
    "header.online": "Trực tuyến",
    "header.offline": "Ngoại tuyến",
    "header.backend_down": "Backend lỗi",
    "header.ready": "Sẵn sàng",
    "header.error": "Lỗi",

    "status.backend_label": "Backend:",
    "status.test_btn": "Kiểm tra",
    "status.testing": "Đang kiểm tra…",
    "status.test_ok": "✅ Backend hoạt động tại {url}",
    "status.test_fail": "❌ Không kết nối được {url}. Container docker đã chạy chưa?",
    "status.unreachable_hint":
      "⚠ Không kết nối được {url}. Chạy `docker compose -f docker-compose.dev.yml up -d` rồi tải lại.",
    "status.sw_unreachable": "Không liên lạc được service worker: {msg}",

    "auth.heading": "Đăng nhập",
    "auth.hint":
      "Dùng email/mật khẩu từ backend MailGuard-AI. Hoạt động trên mọi phiên bản Chrome, không cần Google OAuth.",
    "auth.email": "Email",
    "auth.password": "Mật khẩu",
    "auth.signin": "Đăng nhập",
    "auth.signout": "Đăng xuất",
    "auth.register": "Đăng ký",
    "auth.signing_in": "Đang đăng nhập…",
    "auth.registering": "Đang tạo tài khoản…",
    "auth.success": "Thành công — đang tải bảng điều khiển…",
    "auth.required": "Vui lòng nhập email và mật khẩu.",
    "auth.signed_out": "Đã đăng xuất.",
    "auth.network_err": 'Không kết nối được backend. Kiểm tra "{url}" đã chạy chưa.',
    "auth.bad_credentials": "Sai email hoặc mật khẩu (hoặc tài khoản chưa tồn tại).",
    "auth.validation_err": "Lỗi dữ liệu: {msg}",
    "auth.rate_limited": "Quá nhiều lần đăng nhập. Vui lòng đợi 1 phút rồi thử lại.",

    "auth.advanced_backend": "Cần đổi backend khác?",
    "auth.advanced_hint":
      "URL phía trên được đọc từ <code>chrome.storage.local.mg_base_url</code>. Mở Cài đặt để đổi, hoặc chạy trong DevTools console:",
    "auth.oauth_heading": "Đăng nhập bằng Google (Gmail OAuth)",
    "auth.oauth_hint":
      "Cần OAuth client của Chrome Extension trong Google Cloud project. Service worker cổ điển chưa hỗ trợ luồng Gmail — tạm thời hãy dùng email/mật khẩu phía trên.",
    "auth.oauth_btn": "Kết nối Gmail (sắp ra mắt)",

    "settings.link": "⚙ Cài đặt",

    "dashboard.greeting": "Xin chào, {name}",
    "dashboard.wave": "👋",
    "dashboard.recent_title": "📊 Lịch sử dự đoán gần đây",
    "dashboard.recent_hint": "(từ máy chủ)",
    "dashboard.role_prefix": "Vai trò",

    "stat.predictions": "Lượt quét",
    "stat.risks": "Cảnh báo",
    "stat.avg_risk": "Rủi ro TB",

    "empty.recent": "Chưa có lượt quét nào.",
    "empty.scan": "Chưa quét lần nào.",

    "gmail.heading": "Gmail",
    "gmail.connected": "Đã kết nối Gmail",
    "gmail.not_connected": "Chưa kết nối",
    "gmail.connect": "Kết nối Gmail",
    "gmail.connecting": "Đang kết nối…",
    "gmail.disconnect": "Ngắt kết nối",
    "gmail.disconnecting": "Đang ngắt…",
    "gmail.scan_now": "Quét hộp thư ngay",
    "gmail.scanning": "Đang quét…",
    "gmail.scan_status_ok": "✅ Đã quét {count} thư.",
    "gmail.last_scan_prefix": "Lần quét cuối: ",
    "gmail.connect_to_scan": "Kết nối Gmail để quét hộp thư.",
    "gmail.scan_results_title": "📬 Kết quả quét hộp thư Gmail",
    "gmail.scan_results_hint": "(vừa quét)",
    "gmail.mode_passive": "Chế độ: thủ công · mỗi lần {size} thư",
    "gmail.mode_active": "Chế độ: tự động (quét mỗi 5 phút) · mỗi lần {size} thư",
    "gmail.mode_set": "Đã đặt chế độ: {mode}.",
    "gmail.active_toggle": "Quét tự động (mỗi 5 phút)",
    "gmail.active_toggle_notify": "Thông báo khi phát hiện email nguy hiểm",
    "gmail.notif_block": "Bạn có thể tắt thông báo trong cài đặt Chrome.",
    "gmail.notif_enabled_msg": "✅ Sẽ thông báo khi phát hiện email rủi ro cao.",
    "gmail.notify_threshold_label": "Ngưỡng cảnh báo",

    "item.risk": "Rủi ro",
    "item.error_pill": "lỗi",
    "item.no_subject": "(không có tiêu đề)",
    "item.explanation_btn": "Tại sao?",
    "item.explanation_title": "Giải thích từ AI",
    "item.spans_heading": "Cụm từ đáng ngờ",
    "item.urls_heading": "Liên kết đáng ngờ",
    "item.spans_empty": "Không phát hiện cụm từ rủi ro cụ thể.",
    "item.urls_empty": "Không tìm thấy liên kết đáng ngờ.",
    "item.open_in_gmail": "Mở trong Gmail",

    "notification.danger_title": "⚠️ Email nguy hiểm!",
    "notification.danger_message":
      "Phát hiện email rủi ro cao từ {sender}: {subject}",
  },
};

let currentLocale = "en";

function interpolate(template, vars) {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, name) =>
    vars[name] == null ? `{${name}}` : String(vars[name])
  );
}

export function t(key, vars) {
  const table = STRINGS[currentLocale] || STRINGS.en;
  const fallback = STRINGS.en[key];
  const template = table[key] ?? fallback ?? key;
  return interpolate(template, vars);
}

export async function setLocale(loc) {
  if (!STRINGS[loc]) return;
  currentLocale = loc;
  try {
    await chrome.storage.local.set({ [STORAGE_KEY]: loc });
  } catch {
    // storage may be unavailable in test contexts; ignore.
  }
}

export async function loadLocale() {
  try {
    const stored = await chrome.storage.local.get([STORAGE_KEY]);
    const loc = stored[STORAGE_KEY];
    if (loc && STRINGS[loc]) {
      currentLocale = loc;
    } else {
      // Default to Vietnamese since the project target users are Vietnamese.
      currentLocale = "vi";
    }
  } catch {
    currentLocale = "vi";
  }
  return currentLocale;
}

export function getLocale() {
  return currentLocale;
}

export function availableLocales() {
  return Object.keys(STRINGS);
}

/**
 * Apply translations to elements that carry a `data-i18n="key"` attribute
 * (text content), `data-i18n-placeholder="key"` (placeholder), or
 * `data-i18n-html="key"` (innerHTML — only for trusted strings).
 */
export function applyI18n(root = document) {
  root.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.getAttribute("data-i18n"));
  });
  root.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.setAttribute("placeholder", t(el.getAttribute("data-i18n-placeholder")));
  });
  root.querySelectorAll("[data-i18n-html]").forEach((el) => {
    el.innerHTML = t(el.getAttribute("data-i18n-html"));
  });
}