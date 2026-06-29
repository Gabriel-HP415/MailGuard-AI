/**
 * MailGuard-AI — API client (used by content scripts, popup, and options).
 *
 * Wraps the backend HTTP API with:
 *  - Token storage (chrome.storage.local)
 *  - Base URL config
 *  - Fetch with JSON + error handling
 *  - Helpful error messages for the UI layer
 *
 * Auth flow:
 *   signInWithGoogle() (lib/firebase.js) → exchanges Firebase ID token for our
 *   own JWT at POST /api/v1/auth/firebase/login. Subsequent requests use
 *   that JWT via Authorization: Bearer.
 */

import { getBackendToken } from "./firebase.js";

const STORAGE_KEYS = {
  BASE_URL: "mg_base_url",
  TOKEN: "mg_token",
  USER: "mg_user",
};

const DEFAULT_BASE_URL = "http://localhost:8000/api/v1";

class MailGuardAPI {
  constructor() {
    this.baseUrl = DEFAULT_BASE_URL;
    this.token = null;
    this.user = null;
  }

  async loadConfig() {
    const stored = await chrome.storage.local.get([
      STORAGE_KEYS.BASE_URL,
      STORAGE_KEYS.TOKEN,
      STORAGE_KEYS.USER,
    ]);
    this.baseUrl = stored[STORAGE_KEYS.BASE_URL] || DEFAULT_BASE_URL;
    this.token = stored[STORAGE_KEYS.TOKEN] || null;
    this.user = stored[STORAGE_KEYS.USER] || null;
    return this;
  }

  async saveConfig({ baseUrl, token, user }) {
    const payload = {};
    if (baseUrl !== undefined) payload[STORAGE_KEYS.BASE_URL] = baseUrl;
    if (token !== undefined) payload[STORAGE_KEYS.TOKEN] = token;
    if (user !== undefined) payload[STORAGE_KEYS.USER] = user;
    await chrome.storage.local.set(payload);
    if (baseUrl !== undefined) this.baseUrl = baseUrl;
    if (token !== undefined) this.token = token;
    if (user !== undefined) this.user = user;
  }

  async clearAuth() {
    await chrome.storage.local.remove([STORAGE_KEYS.TOKEN, STORAGE_KEYS.USER]);
    this.token = null;
    this.user = null;
  }

  isAuthenticated() {
    return Boolean(this.token);
  }

  async _request(path, { method = "GET", body = null, auth = true } = {}) {
    const url = `${this.baseUrl}${path}`;
    const headers = { "Content-Type": "application/json" };
    if (auth) {
      // Prefer the backend JWT (issued by /auth/firebase/login); fall back
      // to the cached token in case Firebase auth hasn't been wired up yet
      // (legacy local-dev login flow).
      let token = this.token;
      if (!token) {
        try {
          token = await getBackendToken();
        } catch {
          // No Firebase session; let the request go without a token —
          // public endpoints (register/login) handle their own auth.
        }
      }
      if (token) headers["Authorization"] = `Bearer ${token}`;
    }
    const opts = { method, headers };
    if (body !== null) opts.body = JSON.stringify(body);
    const resp = await fetch(url, opts);
    const text = await resp.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch (err) {
      // Not JSON; ignore
    }
    if (!resp.ok) {
      const msg =
        (data && data.error && data.error.message) ||
        text ||
        `HTTP ${resp.status}`;
      const error = new Error(msg);
      error.status = resp.status;
      error.body = data;
      throw error;
    }
    return data;
  }

  // ---------- Auth ----------
  async register(payload) {
    return this._request("/auth/register", { method: "POST", body: payload, auth: false });
  }

  async login(payload) {
    const data = await this._request("/auth/login", { method: "POST", body: payload, auth: false });
    await this.saveConfig({ token: data.access_token });
    return data;
  }

  async logout() {
    await this.clearAuth();
  }

  async me() {
    return this._request("/auth/me");
  }

  // ---------- Emails & Predictions ----------
  async predict(email, options = {}) {
    const body = {
      email,
      model_version: options.modelVersion || null,
      include_explanation: options.includeExplanation !== false,
    };
    return this._request("/predictions", { method: "POST", body });
  }

  async listPredictions(params = {}) {
    const qs = new URLSearchParams();
    if (params.limit) qs.set("limit", params.limit);
    if (params.offset) qs.set("offset", params.offset);
    if (params.predicted_class) qs.set("predicted_class", params.predicted_class);
    const tail = qs.toString();
    return this._request(`/predictions${tail ? `?${tail}` : ""}`);
  }

  // ---------- Feedback ----------
  async sendFeedback(payload) {
    return this._request("/feedback", { method: "POST", body: payload });
  }

  // ---------- Whitelist / Blacklist ----------
  async getWhitelist() {
    return this._request("/lists/whitelist");
  }
  async addWhitelist(payload) {
    return this._request("/lists/whitelist", { method: "POST", body: payload });
  }
  async removeWhitelist(id) {
    return this._request(`/lists/whitelist/${id}`, { method: "DELETE" });
  }

  async getBlacklist() {
    return this._request("/lists/blacklist");
  }
  async addBlacklist(payload) {
    return this._request("/lists/blacklist", { method: "POST", body: payload });
  }
  async removeBlacklist(id) {
    return this._request(`/lists/blacklist/${id}`, { method: "DELETE" });
  }

  // ---------- Dashboard ----------
  async getStats(days = 30) {
    return this._request(`/dashboard/stats?days=${days}`);
  }
  async getRecent(limit = 10) {
    return this._request(`/dashboard/recent?limit=${limit}`);
  }
  async getAIHealth() {
    return this._request("/dashboard/ai/health");
  }
}

// Singleton instance shared across content scripts, the popup, and the
// background service worker. We export it via ES modules and also attach
// it to the available global object so non-module scripts can use it too.
const api = new MailGuardAPI();
export { api };
export default api;

// Expose to `window` for content scripts / popup / options (classic scripts).
if (typeof window !== "undefined") {
  window.MailGuardAPI = api;
}
// Expose to `self` / `globalThis` for the service worker + popup.
else if (typeof self !== "undefined") {
  self.MailGuardAPI = api;
}
else if (typeof globalThis !== "undefined") {
  globalThis.MailGuardAPI = api;
}