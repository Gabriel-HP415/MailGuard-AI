/**
 * MailGuard-AI — Background service worker (NON-MODULE).
 *
 * This is the fallback SW for environments where `type: module` for SW is
 * unavailable (Chrome < 111, or strict corp-policy installs). All work is
 * done inline using `globalThis`; nothing is imported.
 *
 * Keep this file dependency-free — Chrome MV3 service workers only load a
 * single file from the manifest `service_worker` field. If you need to share
 * code with the popup/options, expose it via `chrome.runtime.getURL('lib/...')`
 * and let them do their own dynamic import() at the call site.
 *
 * The module version (`service-worker.module.js`) is still available for
 * dev environments on Chrome >= 111; flip the manifest by changing the
 * `background.service_worker` field.
 */

// ---------- Constants ----------
const STORAGE_KEYS = {
  BASE_URL: "mg_base_url",
  TOKEN: "mg_token",
  USER: "mg_user",
  FIREBASE_EMAIL: "firebase_email",
  FIREBASE_DISPLAY_NAME: "firebase_display_name",
  FIREBASE_PHOTO_URL: "firebase_photo_url",
  GMAIL_CONNECTED: "mg_gmail_connected",
  GMAIL_MODE: "mg_gmail_mode",           // "passive" | "active"
  GMAIL_BATCH_SIZE: "mg_gmail_batch_size",
  GMAIL_LAST_SCAN_AT: "mg_gmail_last_scan_at",
  GMAIL_SCAN_RESULTS: "mg_gmail_scan_results",
  GMAIL_NOTIFY: "mg_gmail_notify",       // boolean: show OS notification on risky email
  GMAIL_NOTIFY_THRESHOLD: "mg_gmail_notify_threshold", // risk_score (0-100) trigger
};

const DEFAULT_BASE_URL = "https://mailguard-ai-y0nh.onrender.com/api/v1";
const DEFAULT_PORT_BASE_URL = "http://127.0.0.1:8003/api/v1";

// Additional URLs we'll try, in order, when no base URL has been stored.
// If one of them responds on /health, we persist it as the new default so
// the popup shows the right one on next open.
const CANDIDATE_LOCAL_URLS = [
  "http://127.0.0.1:8003/api/v1",
  "http://localhost:8003/api/v1",
  "http://127.0.0.1:8000/api/v1",
  "http://localhost:8000/api/v1",
];

// Required Gmail OAuth scopes (must match manifest.oauth2.scopes).
const GMAIL_SCOPES = [
  "https://www.googleapis.com/auth/gmail.readonly",
  "https://www.googleapis.com/auth/gmail.modify",
];

const GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me";
const POLL_ALARM = "mailguard-gmail-poll";
const POLL_INTERVAL_MINUTES = 5;

async function probeHealth(baseUrl) {
  try {
    const resp = await fetch(`${baseUrl}/health`, {
      method: "GET",
      cache: "no-store",
      signal: AbortSignal.timeout(2000),
    });
    if (!resp.ok) return false;
    const data = await resp.json();
    return data && data.status === "ok";
  } catch {
    return false;
  }
}

async function autoDetectBaseUrl() {
  // Run all candidates in parallel; pick the first one that responds OK.
  const results = await Promise.all(
    CANDIDATE_LOCAL_URLS.map(async (url) => ({
      url,
      ok: await probeHealth(url),
    })),
  );
  const working = results.find((r) => r.ok);
  if (working) {
    await chrome.storage.local.set({ [STORAGE_KEYS.BASE_URL]: working.url });
    return working.url;
  }
  return null;
}

async function getBaseUrl() {
  const stored = await chrome.storage.local.get([STORAGE_KEYS.BASE_URL]);
  if (stored[STORAGE_KEYS.BASE_URL]) return stored[STORAGE_KEYS.BASE_URL];
  // First-time user or after a reset: try to auto-detect a local backend.
  const detected = await autoDetectBaseUrl();
  return detected || DEFAULT_BASE_URL;
}

async function getAuthHeader() {
  const stored = await chrome.storage.local.get([STORAGE_KEYS.TOKEN]);
  if (!stored[STORAGE_KEYS.TOKEN]) return {};
  return { Authorization: `Bearer ${stored[STORAGE_KEYS.TOKEN]}` };
}

async function postJson(path, body) {
  const baseUrl = await getBaseUrl();
  const auth = await getAuthHeader();
  let resp;
  try {
    resp = await fetch(`${baseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...auth },
      body: JSON.stringify(body),
    });
  } catch (err) {
    const err2 = new Error(
      `Cannot reach backend at ${baseUrl}. ` +
      `Is the docker container running and port 8003 forwarded? (${err.message})`
    );
    err2.status = 0;
    throw err2;
  }
  return parseResponse(resp);
}

async function getJson(path) {
  const baseUrl = await getBaseUrl();
  const auth = await getAuthHeader();
  let resp;
  try {
    resp = await fetch(`${baseUrl}${path}`, {
      headers: { "Content-Type": "application/json", ...auth },
    });
  } catch (err) {
    const err2 = new Error(
      `Cannot reach backend at ${baseUrl}. (${err.message})`
    );
    err2.status = 0;
    throw err2;
  }
  return parseResponse(resp);
}

async function parseResponse(resp) {
  const text = await resp.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch {}
  if (!resp.ok) {
    const raw = (data && data.error && data.error.message) || text || `HTTP ${resp.status}`;
    // Be helpful about common endpoints
    let msg = raw;
    if (resp.status === 401 && /credentials/i.test(String(raw))) {
      msg = "Wrong email or password.";
    } else if (resp.status === 422) {
      msg = `Invalid input: ${raw}`;
    } else if (resp.status === 429) {
      msg = "Too many requests — wait a minute and try again.";
    } else if (resp.status >= 500) {
      msg = `Server error: ${raw}`;
    }
    const err = new Error(msg);
    err.status = resp.status;
    err.body = data;
    throw err;
  }
  return data;
}

// ---------- Gmail (inlined from lib/gmail.js) ----------
let _gmailCachedToken = null;
let _gmailCachedTokenExpiresAt = 0;

async function getGmailAccessToken({ interactive = true } = {}) {
  const now = Date.now();
  if (_gmailCachedToken && now < _gmailCachedTokenExpiresAt - 30_000) {
    return _gmailCachedToken;
  }
  const token = await new Promise((resolve, reject) => {
    chrome.identity.getAuthToken({ interactive }, (result) => {
      if (chrome.runtime.lastError || !result) {
        reject(new Error(chrome.runtime.lastError?.message || "No token"));
        return;
      }
      resolve(result);
    });
  });
  _gmailCachedToken = token;
  _gmailCachedTokenExpiresAt = now + 50 * 60 * 1000;
  return token;
}

async function revokeGmailAccess() {
  if (!_gmailCachedToken) return;
  return new Promise((resolve) => {
    chrome.identity.removeCachedAuthToken({ token: _gmailCachedToken }, () => {
      const old = _gmailCachedToken;
      _gmailCachedToken = null;
      _gmailCachedTokenExpiresAt = 0;
      fetch(`https://accounts.google.com/o/oauth2/revoke?token=${old}`)
        .catch(() => {})
        .finally(resolve);
    });
  });
}

async function gmailFetch(path, { method = "GET", params } = {}) {
  let token = await getGmailAccessToken({ interactive: false });
  let url = `${GMAIL_API_BASE}${path}`;
  if (params) {
    const qs = new URLSearchParams(params).toString();
    if (qs) url += `?${qs}`;
  }
  let resp = await fetch(url, {
    method,
    headers: { Authorization: `Bearer ${token}` },
  });
  if (resp.status === 401) {
    _gmailCachedToken = null;
    _gmailCachedTokenExpiresAt = 0;
    token = await getGmailAccessToken({ interactive: true });
    resp = await fetch(url, {
      method,
      headers: { Authorization: `Bearer ${token}` },
    });
  }
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Gmail API ${resp.status}: ${text.slice(0, 300)}`);
  }
  return resp.json();
}

async function listInbox({ maxResults = 50, query = "in:inbox" } = {}) {
  const data = await gmailFetch("/messages", { params: { maxResults, q: query } });
  return data.messages || [];
}

async function getMessage(messageId, { format = "full" } = {}) {
  return gmailFetch(`/messages/${encodeURIComponent(messageId)}`, {
    params: { format },
  });
}

function decodeBase64Url(data) {
  if (!data) return "";
  const normalized = data.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
  try {
    const binary = atob(padded);
    return decodeURIComponent(
      Array.from(binary)
        .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join(""),
    );
  } catch (err) {
    console.warn("[MailGuard] Gmail body decode failed", err);
    return "";
  }
}

function extractEmailContent(msg) {
  const headers = msg?.payload?.headers || [];
  const header = (name) =>
    headers.find((h) => h.name.toLowerCase() === name.toLowerCase())?.value || "";
  const subject = header("Subject");
  const from = header("From");
  const to = header("To");
  const date = header("Date");
  let bodyText = "";
  let bodyHtml = "";
  const attachments = [];
  function walk(part) {
    if (!part) return;
    const mime = (part.mimeType || "").toLowerCase();
    if (part.filename) {
      attachments.push({
        name: part.filename,
        mimeType: mime,
        size: part.body?.size || 0,
        attachmentId: part.body?.attachmentId || null,
      });
    }
    if (mime === "text/plain" && !bodyText && part.body?.data) {
      bodyText = decodeBase64Url(part.body.data);
    } else if (mime === "text/html" && !bodyHtml && part.body?.data) {
      bodyHtml = decodeBase64Url(part.body.data);
    }
    if (Array.isArray(part.parts)) {
      for (const child of part.parts) walk(child);
    }
  }
  walk(msg.payload);
  return {
    id: msg.id,
    threadId: msg.threadId,
    subject, from, to, date,
    snippet: msg.snippet || "",
    body_text: bodyText,
    body_html: bodyHtml,
    attachments,
    labelIds: msg.labelIds || [],
  };
}

async function fetchDecodedInbox({ maxResults = 25 } = {}) {
  const stubs = await listInbox({ maxResults });
  const results = [];
  for (const stub of stubs) {
    try {
      const full = await getMessage(stub.id);
      results.push(extractEmailContent(full));
    } catch (err) {
      console.warn(`[MailGuard] skipping message ${stub.id}:`, err.message);
    }
  }
  return results;
}

async function isGmailAuthorised() {
  try {
    await getGmailAccessToken({ interactive: false });
    return true;
  } catch {
    return false;
  }
}

// ---------- Gmail scan (inlined from background/gmail-watcher.js) ----------
function deriveSenderDomain(fromHeader) {
  if (!fromHeader) return null;
  const m = String(fromHeader).match(/<[^>]*@([^>]+)>/) || String(fromHeader).match(/@([^\s>]+)/);
  if (!m) return null;
  return m[1].toLowerCase();
}

/** Convert a Gmail header date (RFC 2822) into an ISO datetime string.
 * Returns null when the input is missing or unparseable so Pydantic's
 * Optional[datetime] can accept null instead of raising 422.
 */
function normalizeReceivedAt(raw) {
  if (!raw) return null;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}

/** Show an OS notification when a scanned email crosses the risk threshold.
 * Falls back silently if the notifications API is unavailable or the user
 * hasn't enabled the toggle. Notification id encodes the threadId/messageId
 * so onClicked can build a Gmail deep-link.
 */
async function notifyDanger({ subject, from, riskScore, threatLevel, messageId, threadId }) {
  try {
    const cfg = await chrome.storage.local.get([
      STORAGE_KEYS.GMAIL_NOTIFY,
      STORAGE_KEYS.GMAIL_NOTIFY_THRESHOLD,
    ]);
    if (!cfg[STORAGE_KEYS.GMAIL_NOTIFY]) return;
    const threshold = Number(cfg[STORAGE_KEYS.GMAIL_NOTIFY_THRESHOLD]) || 60;
    if ((riskScore || 0) < threshold) return;
    if (!chrome.notifications || !chrome.notifications.create) return;
    const id = `mailguard-danger-${messageId || "x"}-${Date.now()}`;
    // Store the link target so onClicked can read it back (the notification
    // payload itself doesn't survive across SW restarts reliably).
    await chrome.storage.local.set({
      [`mailguard_notif_${id}`]: { threadId, messageId, at: Date.now() },
    });
    // Trim old notification keys so storage doesn't grow forever.
    await pruneNotificationTargets();
    await chrome.notifications.create(id, {
      type: "basic",
      iconUrl: "icons/icon128.png",
      title: "⚠️ Email nguy hiểm — MailGuard-AI",
      message: `Phát hiện email rủi ro cao (${Math.round(riskScore)}/100)`,
      contextMessage: `${from || "(không rõ người gửi)"} — ${subject || "(không có tiêu đề)"}`,
      priority: 2,
      requireInteraction: true,
    });
  } catch (err) {
    console.warn("[MailGuard] notifyDanger failed:", err.message);
  }
}

/** Remove notification target keys older than 1 hour so storage doesn't grow. */
async function pruneNotificationTargets() {
  try {
    const all = await chrome.storage.local.get(null);
    const cutoff = Date.now() - 60 * 60 * 1000;
    const stale = Object.keys(all).filter(
      (k) => k.startsWith("mailguard_notif_") && (all[k]?.at || 0) < cutoff
    );
    if (stale.length) await chrome.storage.local.remove(stale);
  } catch (err) {
    // best effort
  }
}

/** Build a Gmail deep link from a threadId/messageId pair. The standard
 * pattern is https://mail.google.com/mail/u/0/#inbox/{threadId}; using
 * threadId keeps the user inside the conversation even if the original
 * message has replies.
 */
function buildGmailUrl({ threadId, messageId }) {
  const base = "https://mail.google.com/mail/u/0/";
  if (threadId) return `${base}#inbox/${threadId}`;
  if (messageId) return `${base}#search/in%3Aanywhere%20rfc822msgid%3A${encodeURIComponent(messageId)}`;
  return base;
}

async function runGmailScan() {
  const token = await getGmailAccessToken({ interactive: false });
  if (!token) {
    throw new Error("Gmail access token not granted");
  }
  const cfg = await chrome.storage.local.get([STORAGE_KEYS.GMAIL_BATCH_SIZE]);
  const batchSize = Number(cfg[STORAGE_KEYS.GMAIL_BATCH_SIZE]) || 25;
  const emails = await fetchDecodedInbox({ maxResults: batchSize });
  if (!emails.length) {
    await chrome.storage.local.set({
      [STORAGE_KEYS.GMAIL_LAST_SCAN_AT]: new Date().toISOString(),
      [STORAGE_KEYS.GMAIL_SCAN_RESULTS]: [],
    });
    return [];
  }
  const baseUrl = await getBaseUrl();
  const auth = await getAuthHeader();
  const results = [];
  for (const email of emails) {
    try {
      // Backend schema (app/schemas/email.py::EmailCreate) requires:
      //  - sender: str (min 1, max 255)
      //  - subject: optional str (max 1000)
      //  - body_text / body_html: optional str
      //  - links: optional list[str]
      //  - attachments: optional list[dict]
      //  - received_at: optional datetime (ISO 8601)
      // Gmail sometimes returns empty/missing fields; normalise before sending.
      const sender = String(email.from || "").trim() || "unknown@unknown";
      const payload = {
        email: {
          sender,
          sender_domain: deriveSenderDomain(email.from),
          recipient: email.to || null,
          subject: email.subject || null,
          body_text: (email.body_text || "").slice(0, 8000),
          body_html: null,
          links: [],
          attachments: Array.isArray(email.attachments) ? email.attachments : [],
          received_at: normalizeReceivedAt(email.date),
        },
        model_version: null,
        include_explanation: true,
      };
      const resp = await fetch(`${baseUrl}/predictions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...auth },
        body: JSON.stringify(payload),
      });
      const data = await parseResponse(resp);
      const result = {
        messageId: email.id,
        threadId: email.threadId,
        subject: email.subject,
        from: email.from,
        snippet: email.snippet,
        prediction: {
          predicted_class: data.predicted_class,
          class_index: data.class_index,
          confidence: data.confidence,
          risk_score: data.risk_score,
          threat_level: data.threat_level,
          explanation: data.explanation ?? null,
          highlighted_spans: Array.isArray(data.highlighted_spans) ? data.highlighted_spans : [],
          suspicious_urls: data.suspicious_urls ?? [],
        },
        scanned_at: new Date().toISOString(),
      };
      results.push(result);
      // Fire OS notification if the user opted in and the risk is high enough.
      await notifyDanger({
        subject: email.subject,
        from: email.from,
        riskScore: data.risk_score,
        threatLevel: data.threat_level,
        messageId: email.id,
        threadId: email.threadId,
      });
    } catch (err) {
      console.warn(`[MailGuard] prediction failed for ${email.id}:`, err.message);
      // Surface backend validation details when DEBUG=true so 422s are actionable.
      const details = err.body?.error?.details;
      results.push({
        messageId: email.id,
        subject: email.subject,
        from: email.from,
        error: details ? `${err.message} · ${JSON.stringify(details)}` : err.message,
        scanned_at: new Date().toISOString(),
      });
    }
  }
  await chrome.storage.local.set({
    [STORAGE_KEYS.GMAIL_LAST_SCAN_AT]: new Date().toISOString(),
    [STORAGE_KEYS.GMAIL_SCAN_RESULTS]: results,
  });
  return results;
}

// Install the periodic alarm on startup/install.
async function ensurePollAlarm() {
  const cfg = await chrome.storage.local.get([STORAGE_KEYS.GMAIL_MODE]);
  const mode = cfg[STORAGE_KEYS.GMAIL_MODE] || "passive";
  try {
    const existing = await chrome.alarms.get(POLL_ALARM);
    if (mode === "active" && !existing) {
      chrome.alarms.create(POLL_ALARM, { periodInMinutes: POLL_INTERVAL_MINUTES });
    } else if (mode !== "active" && existing) {
      chrome.alarms.clear(POLL_ALARM);
    } else if (mode === "active" && existing) {
      chrome.alarms.clear(POLL_ALARM).then(() => {
        chrome.alarms.create(POLL_ALARM, { periodInMinutes: POLL_INTERVAL_MINUTES });
      });
    }
  } catch (err) {
    console.warn("[MailGuard] ensurePollAlarm failed:", err);
  }
}

// ---------- Message router ----------
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    try {
      switch (message.type) {
        case "ping":
          sendResponse({ ok: true, base_url: await getBaseUrl() });
          return;

        case "login": {
          const data = await postJson("/auth/login", message.payload);
          await chrome.storage.local.set({
            [STORAGE_KEYS.TOKEN]: data.access_token,
          });
          // Fetch /me for nice UI display
          try {
            const me = await getJson("/auth/me");
            await chrome.storage.local.set({ [STORAGE_KEYS.USER]: me });
          } catch (err) {
            console.warn("[MailGuard] /auth/me after login failed:", err.message);
          }
          sendResponse({ ok: true, data });
          return;
        }

        case "register": {
          const data = await postJson("/auth/register", message.payload);
          await chrome.storage.local.set({
            [STORAGE_KEYS.TOKEN]: data.access_token,
          });
          try {
            const me = await getJson("/auth/me");
            await chrome.storage.local.set({ [STORAGE_KEYS.USER]: me });
          } catch (err) {
            console.warn("[MailGuard] /auth/me after register failed:", err.message);
          }
          sendResponse({ ok: true, data });
          return;
        }

        case "logout": {
          await chrome.storage.local.remove([STORAGE_KEYS.TOKEN, STORAGE_KEYS.USER]);
          sendResponse({ ok: true });
          return;
        }

        case "get-status": {
          const stored = await chrome.storage.local.get([
            STORAGE_KEYS.TOKEN, STORAGE_KEYS.USER, STORAGE_KEYS.BASE_URL,
            STORAGE_KEYS.GMAIL_CONNECTED, STORAGE_KEYS.GMAIL_MODE,
            STORAGE_KEYS.GMAIL_BATCH_SIZE, STORAGE_KEYS.GMAIL_LAST_SCAN_AT,
            STORAGE_KEYS.GMAIL_NOTIFY, STORAGE_KEYS.GMAIL_NOTIFY_THRESHOLD,
          ]);
          const baseUrl = stored[STORAGE_KEYS.BASE_URL] || DEFAULT_BASE_URL;
          const authenticated = Boolean(stored[STORAGE_KEYS.TOKEN]);
          // Try a non-interactive token check to determine real OAuth state.
          let gmailConnected = Boolean(stored[STORAGE_KEYS.GMAIL_CONNECTED]);
          try {
            gmailConnected = await isGmailAuthorised();
            if (gmailConnected) {
              await chrome.storage.local.set({ [STORAGE_KEYS.GMAIL_CONNECTED]: true });
            }
          } catch {
            // ignore
          }
          sendResponse({
            ok: true,
            authenticated,
            base_url: baseUrl,
            user: stored[STORAGE_KEYS.USER] || null,
            gmail: {
              connected: gmailConnected,
              mode: stored[STORAGE_KEYS.GMAIL_MODE] || "passive",
              batch_size: Number(stored[STORAGE_KEYS.GMAIL_BATCH_SIZE]) || 25,
              last_scan_at: stored[STORAGE_KEYS.GMAIL_LAST_SCAN_AT] || null,
              notify_enabled: Boolean(stored[STORAGE_KEYS.GMAIL_NOTIFY]),
              notify_threshold: Number(stored[STORAGE_KEYS.GMAIL_NOTIFY_THRESHOLD]) || 60,
            },
          });
          return;
        }

        case "set-base-url": {
          await chrome.storage.local.set({ [STORAGE_KEYS.BASE_URL]: message.base_url });
          sendResponse({ ok: true });
          return;
        }

        case "predict": {
          const data = await postJson("/predictions", {
            email: message.payload,
            include_explanation: false,
          });
          sendResponse({ ok: true, data });
          return;
        }

        case "dashboard-stats": {
          const data = await getJson(`/dashboard/stats?days=${message.days || 30}`);
          sendResponse({ ok: true, data });
          return;
        }

        case "dashboard-recent": {
          const data = await getJson(`/dashboard/recent?limit=${message.limit || 10}`);
          sendResponse({ ok: true, data });
          return;
        }

        // ---------- Gmail management ----------
        case "gmail_connect": {
          const token = await getGmailAccessToken({ interactive: true });
          await chrome.storage.local.set({ [STORAGE_KEYS.GMAIL_CONNECTED]: true });
          sendResponse({ ok: true, connected: Boolean(token) });
          return;
        }

        case "gmail_disconnect": {
          await revokeGmailAccess();
          await chrome.storage.local.set({ [STORAGE_KEYS.GMAIL_CONNECTED]: false });
          try { await chrome.alarms.clear(POLL_ALARM); } catch {}
          sendResponse({ ok: true });
          return;
        }

        case "gmail_set_mode": {
          const mode = message.mode === "active" ? "active" : "passive";
          const batch = Math.min(Math.max(Number(message.batch_size) || 25, 1), 100);
          await chrome.storage.local.set({
            [STORAGE_KEYS.GMAIL_MODE]: mode,
            [STORAGE_KEYS.GMAIL_BATCH_SIZE]: batch,
          });
          await ensurePollAlarm();
          sendResponse({ ok: true, mode, batch_size: batch });
          return;
        }

        case "gmail_set_notify": {
          const enabled = Boolean(message.enabled);
          const threshold = Math.min(Math.max(Number(message.threshold) || 60, 1), 100);
          await chrome.storage.local.set({
            [STORAGE_KEYS.GMAIL_NOTIFY]: enabled,
            [STORAGE_KEYS.GMAIL_NOTIFY_THRESHOLD]: threshold,
          });
          sendResponse({ ok: true, enabled, threshold });
          return;
        }

        case "gmail_scan_now": {
          const results = await runGmailScan();
          sendResponse({ ok: true, results });
          return;
        }

        case "gmail_get_results": {
          const stored = await chrome.storage.local.get([
            STORAGE_KEYS.GMAIL_LAST_SCAN_AT,
            STORAGE_KEYS.GMAIL_SCAN_RESULTS,
            STORAGE_KEYS.GMAIL_MODE,
            STORAGE_KEYS.GMAIL_BATCH_SIZE,
          ]);
          sendResponse({
            ok: true,
            last_scan_at: stored[STORAGE_KEYS.GMAIL_LAST_SCAN_AT] || null,
            results: stored[STORAGE_KEYS.GMAIL_SCAN_RESULTS] || [],
            mode: stored[STORAGE_KEYS.GMAIL_MODE] || "passive",
            batch_size: Number(stored[STORAGE_KEYS.GMAIL_BATCH_SIZE]) || 25,
          });
          return;
        }

        default:
          sendResponse({ ok: false, error: `Unknown message type: ${message.type}` });
      }
    } catch (err) {
      console.error(`[MailGuard] handler ${message.type} failed:`, err);
      sendResponse({ ok: false, error: err.message || String(err), status: err.status });
    }
  })();
  // Tell Chrome we'll respond asynchronously.
  return true;
});

// ---------- Gmail alarm wiring ----------
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== POLL_ALARM) return;
  const cfg = await chrome.storage.local.get([STORAGE_KEYS.GMAIL_CONNECTED]);
  if (!cfg[STORAGE_KEYS.GMAIL_CONNECTED]) return;
  try {
    await runGmailScan();
  } catch (err) {
    console.warn("[MailGuard] alarm scan failed:", err.message);
  }
});

// ---------- Notification click → open Gmail ----------
if (chrome.notifications && chrome.notifications.onClicked) {
  chrome.notifications.onClicked.addListener(async (notifId) => {
    try {
      const key = `mailguard_notif_${notifId}`;
      const stored = await chrome.storage.local.get([key]);
      const target = stored[key];
      const url = buildGmailUrl(target || {});
      await chrome.tabs.create({ url });
      await chrome.notifications.clear(notifId);
      await chrome.storage.local.remove([key]);
    } catch (err) {
      console.warn("[MailGuard] notification click handler failed:", err.message);
    }
  });

  chrome.notifications.onClosed.addListener(async (notifId, _byUser) => {
    // Clean up the stored target so storage doesn't grow. Whether user
    // dismissed it or it timed out, the link is no longer actionable.
    try {
      await chrome.storage.local.remove([`mailguard_notif_${notifId}`]);
    } catch {}
  });
}

// ---------- Lifecycle ----------
chrome.runtime.onInstalled.addListener(async () => {
  console.log("[MailGuard-AI] extension installed (non-module SW)");
  await ensurePollAlarm();
});

chrome.runtime.onStartup.addListener(async () => {
  console.log("[MailGuard-AI] service worker startup");
  await ensurePollAlarm();
});