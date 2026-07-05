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
          ]);
          const baseUrl = stored[STORAGE_KEYS.BASE_URL] || DEFAULT_BASE_URL;
          const authenticated = Boolean(stored[STORAGE_KEYS.TOKEN]);
          sendResponse({
            ok: true,
            authenticated,
            base_url: baseUrl,
            user: stored[STORAGE_KEYS.USER] || null,
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

        // Gmail OAuth and watcher handlers are intentionally NOT routed here
        // because they depend on the larger `lib/*.js` modules. When loaded
        // with the module SW (manifest.type=module), those are handled in
        // `service-worker.module.js` instead.
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

// ---------- Lifecycle (kept minimal so it never throws) ----------
chrome.runtime.onInstalled.addListener(() => {
  console.log("[MailGuard-AI] extension installed (non-module SW)");
});

chrome.runtime.onStartup.addListener(() => {
  console.log("[MailGuard-AI] service worker startup");
});