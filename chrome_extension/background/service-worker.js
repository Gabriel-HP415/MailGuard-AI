/**
 * MailGuard-AI — Background service worker (ES module).
 *
 * Loaded as a module via manifest.json's `"type": "module"`. Therefore we
 * use static `import` (NOT `importScripts`) for the API singleton.
 *
 * Responsibilities:
 *  - Handle the popup / options page actions (login, logout, save settings).
 *  - Listen to tab updates to refresh per-tab state.
 *  - Expose a lightweight messaging API to content scripts.
 *  - Bridge Firebase auth events from the popup/options into in-memory state.
 */

import { api } from "../lib/api.js";
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
    console.warn("[MailGuard-AI] Failed to refresh Firebase state", err);
    FIREBASE_STATE.signedIn = false;
    FIREBASE_STATE.profile = null;
  }
}

chrome.runtime.onInstalled.addListener(() => {
  console.log("[MailGuard-AI] Extension installed.");
  refreshFirebaseState();
});

chrome.runtime.onStartup.addListener(() => {
  refreshFirebaseState();
});

refreshFirebaseState();

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    try {
      if (message.type === "ping") {
        sendResponse({ ok: true });
        return;
      }
      if (message.type === "login") {
        await api.loadConfig();
        const data = await api.login(message.payload);
        // Fetch the user profile so the popup can render a display name.
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
        // /auth/register now returns TokenResponse — persist immediately.
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
        await firebaseSignOut();
        await refreshFirebaseState();
        sendResponse({ ok: true });
        return;
      }
      if (message.type === "firebase_signed_in") {
        await refreshFirebaseState();
        // Cache the backend JWT in the API singleton so get-status is truthful.
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
        await refreshFirebaseState();
        sendResponse({
          ok: true,
          authenticated:
            api.isAuthenticated() || FIREBASE_STATE.signedIn,
          user: api.user || {
            email: FIREBASE_STATE.profile?.firebase_email,
            full_name: FIREBASE_STATE.profile?.firebase_display_name,
            avatar_url: FIREBASE_STATE.profile?.firebase_photo_url,
            auth_provider: "firebase",
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