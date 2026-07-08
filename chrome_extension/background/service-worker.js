/**
 * MailGuard-AI — Background service worker (ES module).
 *
 * Loaded as a module via manifest.json's `"type": "module"`. Therefore we
 * use static `import` (NOT `importScripts`) for the API singleton.
 *
 * Responsibilities:
 *  - Handle the popup / options page actions (Google sign-in, settings).
 *  - Wire the Gmail inbox watcher (chrome.alarms + Gmail API client).
 *  - Expose a lightweight messaging API to content scripts.
 *
 * Robustness rules (important in MV3):
 *  - Every top-level chrome.* call that can throw is wrapped in try/catch.
 *  - We do NOT call installGmailWatcher() more than once per SW lifetime.
 *  - Firebase and Gmail state are refreshed lazily on first message.
 */

import "../lib/api.js";
const api = globalThis.MailGuardAPI;
import {
  fetchDecodedInbox,
  getGmailAccessToken,
  isAuthorised as gmailIsAuthorised,
  revokeGmailAccess,
} from "../lib/gmail.js";
import {
  installGmailWatcher,
  runScan as runGmailScan,
  STORAGE_KEYS as WATCHER_STORAGE_KEYS,
} from "./gmail-watcher.js";
import {
  getCurrentUser,
  getBackendToken,
  isSignedIn,
  persistBackendSession,
  signOut as firebaseSignOut,
} from "../lib/firebase.js";

const FIREBASE_STATE = {
  signedIn: false,
  profile: null,
};
const GMAIL_STATE = {
  authorised: false,
  lastScanAt: null,
  lastResults: [],
};

let _watcherInstalled = false;
let _statesInitialised = false;

async function fetchMe(token) {
  const resp = await fetch(`${api.baseUrl}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) {
    throw new Error(`/auth/me failed: ${resp.status}`);
  }
  return resp.json();
}

async function refreshFirebaseState() {
  try {
    FIREBASE_STATE.signedIn = await isSignedIn();
    FIREBASE_STATE.profile = await getCurrentUser();
  } catch (err) {
    // Firebase module may not be initialised in some installs (e.g. when
    // only the Gmail OAuth flow is used). Don't let this take down the SW.
    console.warn("[MailGuard-AI] Failed to refresh Firebase state", err);
    FIREBASE_STATE.signedIn = false;
    FIREBASE_STATE.profile = null;
  }
}

async function refreshGmailState() {
  try {
    GMAIL_STATE.authorised = await gmailIsAuthorised();
  } catch {
    GMAIL_STATE.authorised = false;
  }
  try {
    const store = await chrome.storage.local.get([
      "mg_gmail_last_scan_at",
      "mg_gmail_scan_results",
    ]);
    GMAIL_STATE.lastScanAt = store.mg_gmail_last_scan_at || null;
    GMAIL_STATE.lastResults = store.mg_gmail_scan_results || [];
  } catch {
    GMAIL_STATE.lastScanAt = null;
    GMAIL_STATE.lastResults = [];
  }
}

chrome.runtime.onInstalled.addListener(() => {
  console.log("[MailGuard-AI] Extension installed.");
  ensureWired();
});

chrome.runtime.onStartup.addListener(() => {
  ensureWired();
});

/** Idempotent boot: install watcher + initial state exactly once per
 *  service-worker lifetime. Re-calling on every event listener is what was
 *  previously throwing "Invalid value for argument 1. Expected at most 1"
 *  and killing the SW. */
function ensureWired() {
  if (_watcherInstalled) return;
  _watcherInstalled = true;
  try {
    installGmailWatcher(api);
  } catch (err) {
    console.warn("[MailGuard-AI] installGmailWatcher failed:", err);
  }
  initStates().catch(() => {});
}

/** Refresh Firebase + Gmail state. Safe to call multiple times. */
async function initStates() {
  if (_statesInitialised) return;
  _statesInitialised = true;
  await Promise.all([refreshFirebaseState(), refreshGmailState()]);
}

// Kick off the first boot when the SW is loaded by Chrome. Wrapping in
// try/catch + setTimeout prevents any single failing import / call from
// tearing down the entire SW (which would show as the "extension error"
// badge in chrome://extensions).
setTimeout(() => {
  try {
    ensureWired();
  } catch (err) {
    console.warn("[MailGuard-AI] ensureWired failed:", err);
  }
}, 0);

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    try {
      if (message.type === "ping") {
        sendResponse({ ok: true });
        return;
      }

      if (message.type === "api-request") {
        const { path, method, body } = message.payload;
        const data = await api._request(path, { method, body });
        sendResponse({ ok: true, data });
        return;
      }

      // ----- New Gmail-OAuth flow (replaces legacy email/password login) -----
      if (message.type === "gmail_authorize") {
        const token = await getGmailAccessToken({ interactive: true });
        await refreshGmailState();
        sendResponse({ ok: true, token });
        return;
      }
      if (message.type === "gmail_revoke") {
        await revokeGmailAccess();
        await refreshGmailState();
        sendResponse({ ok: true });
        return;
      }
      if (message.type === "gmail_fetch_inbox") {
        const inbox = await fetchDecodedInbox({
          maxResults: message.maxResults || 25,
        });
        sendResponse({ ok: true, emails: inbox });
        return;
      }
      if (message.type === "gmail_login") {
        // Full flow: get Gmail token, exchange for MailGuard JWT.
        const token = await getGmailAccessToken({ interactive: true });
        await api.loadConfig();
        const data = await api.loginWithGmail({
          access_token: token,
          email: message.payload?.email || null,
        });
        try {
          const user = await fetchMe(data.access_token);
          api.user = user;
          await chrome.storage.local.set({ mg_user: user });
        } catch (err) {
          console.warn("[MailGuard-AI] /auth/me after Gmail login failed", err);
        }
        await refreshGmailState();
        sendResponse({ ok: true, data });
        return;
      }

      // ----- Watcher (single owner of these message types) -----
      if (message.type === "gmail_scan_now") {
        const results = await runGmailScan(api);
        sendResponse({ ok: true, count: results.length });
        return;
      }
      if (message.type === "gmail_get_last_scan") {
        const store = await chrome.storage.local.get([
          WATCHER_STORAGE_KEYS.LAST_SCAN_AT,
          WATCHER_STORAGE_KEYS.SCAN_RESULTS,
        ]);
        sendResponse({ ok: true, ...store });
        return;
      }
      if (message.type === "gmail_set_mode") {
        await chrome.storage.local.set({
          [WATCHER_STORAGE_KEYS.MODE]: message.mode || "passive",
        });
        sendResponse({ ok: true });
        return;
      }

      // ----- Legacy handlers kept for admin / fallback login -----
      if (message.type === "login") {
        await api.loadConfig();
        const data = await api.login(message.payload);
        try {
          const user = await fetchMe(data.access_token);
          await persistBackendSession({
            token: data.access_token,
            expiresIn: data.expires_in,
            user,
          });
          api.token = data.access_token;
          api.user = user;
        } catch (err) {
          console.warn("[MailGuard-AI] /auth/me failed after login", err);
        }
        sendResponse({ ok: true, data });
        return;
      }
      if (message.type === "register") {
        await api.loadConfig();
        const data = await api.register(message.payload);
        try {
          const user = await fetchMe(data.access_token);
          await persistBackendSession({
            token: data.access_token,
            expiresIn: data.expires_in,
            user,
          });
          api.token = data.access_token;
          api.user = user;
        } catch (err) {
          console.warn("[MailGuard-AI] /auth/me failed after register", err);
        }
        sendResponse({ ok: true, data });
        return;
      }
      if (message.type === "logout") {
        await api.clearAuth();
        await revokeGmailAccess();
        await firebaseSignOut();
        await refreshFirebaseState();
        await refreshGmailState();
        sendResponse({ ok: true });
        return;
      }
      if (message.type === "firebase_signed_in") {
        await refreshFirebaseState();
        try {
          const token = await getBackendToken();
          if (token) {
            await api.saveConfig({ token });
          }
        } catch (err) {
          console.warn("[MailGuard-AI] Backend JWT fetch after Firebase login failed", err);
        }
        await refreshFirebaseState();
        sendResponse({ ok: true });
        return;
      }
      if (message.type === "get-status") {
        await api.loadConfig();
        await Promise.all([refreshFirebaseState(), refreshGmailState()]);
        const authorised =
          api.isAuthenticated() ||
          FIREBASE_STATE.signedIn ||
          GMAIL_STATE.authorised;
        sendResponse({
          ok: true,
          authenticated: authorised,
          gmail: {
            authorised: GMAIL_STATE.authorised,
            lastScanAt: GMAIL_STATE.lastScanAt,
            lastResultCount: GMAIL_STATE.lastResults.length,
          },
          user: api.user || {
            email: FIREBASE_STATE.profile?.firebase_email,
            full_name: FIREBASE_STATE.profile?.firebase_display_name,
            avatar_url: FIREBASE_STATE.profile?.firebase_photo_url,
            auth_provider: FIREBASE_STATE.signedIn ? "firebase" : "gmail",
          },
          firebase: FIREBASE_STATE.profile,
          baseUrl: api.baseUrl,
        });
        return;
      }
      sendResponse({ ok: false, error: "Unknown message type" });
    } catch (err) {
      sendResponse({ ok: false, error: err.message });
    }
  })();
  // Returning true keeps the message channel open for the async response.
  return true;
});