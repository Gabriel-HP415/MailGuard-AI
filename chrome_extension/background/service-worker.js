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
 */

import { api } from "../lib/api.js";

chrome.runtime.onInstalled.addListener(() => {
  console.log("[MailGuard-AI] Extension installed.");
});

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
        sendResponse({ ok: true, data });
        return;
      }
      if (message.type === "register") {
        await api.loadConfig();
        const data = await api.register(message.payload);
        sendResponse({ ok: true, data });
        return;
      }
      if (message.type === "logout") {
        await api.clearAuth();
        sendResponse({ ok: true });
        return;
      }
      if (message.type === "get-status") {
        await api.loadConfig();
        sendResponse({
          ok: true,
          authenticated: api.isAuthenticated(),
          user: api.user,
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