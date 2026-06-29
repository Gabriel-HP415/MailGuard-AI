const MAILGUARD_CONFIG = {
  // Default backend URL. Override by setting `localStorage.mg_baseUrl`.
  defaultBaseUrl: (window.MAILGUARD_API_BASE_URL || "http://localhost:8000/api/v1"),
  storageKeys: {
    baseUrl: "mg_baseUrl",
    token: "mg_token",
    user: "mg_user",
  },
};

class MailGuardAPI {
  constructor() {
    this.baseUrl = MAILGUARD_CONFIG.defaultBaseUrl;
    this.token = null;
    this.user = null;
  }

  loadConfig() {
    this.baseUrl = localStorage.getItem(MAILGUARD_CONFIG.storageKeys.baseUrl)
      || MAILGUARD_CONFIG.defaultBaseUrl;
    this.token = localStorage.getItem(MAILGUARD_CONFIG.storageKeys.token);
    try {
      const raw = localStorage.getItem(MAILGUARD_CONFIG.storageKeys.user);
      this.user = raw ? JSON.parse(raw) : null;
    } catch (err) {
      this.user = null;
    }
  }

  saveConfig({ baseUrl, token, user }) {
    if (baseUrl !== undefined) {
      this.baseUrl = baseUrl;
      localStorage.setItem(MAILGUARD_CONFIG.storageKeys.baseUrl, baseUrl);
    }
    if (token !== undefined) {
      this.token = token;
      if (token === null) localStorage.removeItem(MAILGUARD_CONFIG.storageKeys.token);
      else localStorage.setItem(MAILGUARD_CONFIG.storageKeys.token, token);
    }
    if (user !== undefined) {
      this.user = user;
      if (user === null) localStorage.removeItem(MAILGUARD_CONFIG.storageKeys.user);
      else localStorage.setItem(MAILGUARD_CONFIG.storageKeys.user, JSON.stringify(user));
    }
  }

  isAuthenticated() {
    return Boolean(this.token);
  }

  isAdmin() {
    return Boolean(this.user && this.user.role === "admin");
  }

  async _request(path, { method = "GET", body = null, auth = true } = {}) {
    const url = `${this.baseUrl}${path}`;
    const headers = { "Content-Type": "application/json" };
    if (auth && this.token) headers["Authorization"] = `Bearer ${this.token}`;
    const opts = { method, headers };
    if (body !== null) opts.body = JSON.stringify(body);

    const resp = await fetch(url, opts);
    const text = await resp.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (err) { /* ignore */ }

    if (!resp.ok) {
      const msg = (data && data.error && data.error.message) || text || `HTTP ${resp.status}`;
      const err = new Error(msg);
      err.status = resp.status;
      err.body = data;
      if (resp.status === 401) this.saveConfig({ token: null, user: null });
      throw err;
    }
    return data;
  }

  // ---------- Auth ----------
  async login(payload) {
    const data = await this._request("/auth/login", { method: "POST", body: payload, auth: false });
    this.saveConfig({ token: data.access_token });
    const me = await this._request("/auth/me");
    this.saveConfig({ user: me });
    return me;
  }

  async register(payload) {
    const data = await this._request("/auth/register", { method: "POST", body: payload, auth: false });
    return data;
  }

  async logout() {
    this.saveConfig({ token: null, user: null });
  }

  async me() {
    return this._request("/auth/me");
  }

  // ---------- Predictions ----------
  async predict(payload) {
    return this._request("/predictions", { method: "POST", body: payload });
  }

  async listPredictions(params = {}) {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v != null && qs.set(k, v));
    const tail = qs.toString();
    return this._request(`/predictions${tail ? `?${tail}` : ""}`);
  }

  async getPrediction(id) {
    return this._request(`/predictions/${id}`);
  }

  // ---------- Feedback ----------
  async sendFeedback(payload) {
    return this._request("/feedback", { method: "POST", body: payload });
  }

  // ---------- Whitelist / Blacklist ----------
  async getWhitelist()       { return this._request("/lists/whitelist"); }
  async addWhitelist(p)      { return this._request("/lists/whitelist", { method: "POST", body: p }); }
  async removeWhitelist(id)  { return this._request(`/lists/whitelist/${id}`, { method: "DELETE" }); }

  async getBlacklist()       { return this._request("/lists/blacklist"); }
  async addBlacklist(p)      { return this._request("/lists/blacklist", { method: "POST", body: p }); }
  async removeBlacklist(id)  { return this._request(`/lists/blacklist/${id}`, { method: "DELETE" }); }

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

  // ---------- Admin ----------
  async listModels()                    { return this._request("/admin/models"); }
  async createModel(p)                  { return this._request("/admin/models", { method: "POST", body: p }); }
  async updateModel(id, p)              { return this._request(`/admin/models/${id}`, { method: "PATCH", body: p }); }
  async activateModel(id)               { return this._request(`/admin/models/${id}/activate`, { method: "POST" }); }
}

const api = new MailGuardAPI();
api.loadConfig();