/**
 * MailGuard-AI — Popup logic.
 *
 * Flow:
 *   1. On open: load stored locale (default VI), apply i18n, then ask SW for
 *      `get-status` to discover current base URL + auth state.
 *   2. Always show the backend URL in the status strip (debug-friendly).
 *   3. Sign-in / Gmail scan: send message to SW (classic) which performs the
 *      network call and returns {ok, data} | {ok: false, error}.
 */

import {
  t,
  applyI18n,
  loadLocale,
  setLocale,
  getLocale,
} from "../lib/i18n.js";

(async function initPopup() {
  // ---- Load locale & translate static UI ----
  await loadLocale();
  applyI18n(document);
  updateLangToggleLabel();

  const authStatus = document.getElementById("auth-status");
  const statusPill = document.getElementById("status-pill");
  const backendUrlEl = document.getElementById("backend-url");
  const testConnectionBtn = document.getElementById("test-connection-btn");
  const langToggle = document.getElementById("lang-toggle");

  const loginForm = document.getElementById("login-form");
  const emailInput = document.getElementById("email");
  const passwordInput = document.getElementById("password");
  const loginBtn = loginForm.querySelector("button");
  const loginBtnLabel = document.getElementById("login-btn-label");

  const authSection = document.getElementById("auth-section");
  const dashSection = document.getElementById("dashboard-section");
  const logoutBtn = document.getElementById("logout-btn");
  const openOptions = document.getElementById("open-options");

  const userName = document.getElementById("user-name");
  const userEmail = document.getElementById("user-email");
  const userProvider = document.getElementById("user-provider");
  const userAvatar = document.getElementById("user-avatar");
  const statTotal = document.getElementById("stat-total");
  const statRisks = document.getElementById("stat-risks");
  const statAvg = document.getElementById("stat-avg");
  const recentList = document.getElementById("recent-list");

  // Gmail controls
  const gmailConnectionPill = document.getElementById("gmail-connection-pill");
  const gmailModeLabel = document.getElementById("gmail-mode-label");
  const gmailLastScan = document.getElementById("gmail-last-scan");
  const gmailConnectBtn = document.getElementById("gmail-connect-btn");
  const gmailDisconnectBtn = document.getElementById("gmail-disconnect-btn");
  const gmailScanBtn = document.getElementById("gmail-scan-btn");
  const gmailScanList = document.getElementById("gmail-scan-list");
  const gmailModeToggle = document.getElementById("gmail-mode-toggle");
  const gmailNotifyToggle = document.getElementById("gmail-notify-toggle");
  const gmailStatus = document.getElementById("gmail-status");

  // ---------- Language toggle ----------
  function updateLangToggleLabel() {
    const next = getLocale() === "vi" ? "EN" : "VI";
    const lbl = document.getElementById("lang-toggle-label");
    if (lbl) lbl.textContent = next;
  }

  langToggle.addEventListener("click", async () => {
    const next = getLocale() === "vi" ? "en" : "vi";
    await setLocale(next);
    // Re-render every translatable element on the page.
    applyI18n(document);
    updateLangToggleLabel();
    // Refresh dynamic sections (greeting, stats labels etc. need fresh strings)
    await refreshStatus();
  });

  // ---------- helpers ----------
  function setAuthStatus(msg) {
    authStatus.textContent = msg || "";
  }

  function setBusy(button, busy, busyLabel) {
    if (!button) return;
    if (busy) {
      button.disabled = true;
      button.dataset.originalLabel = button.dataset.originalLabel || button.textContent;
      button.textContent = busyLabel || t("status.testing");
    } else {
      button.disabled = false;
      if (button.dataset.originalLabel) {
        button.textContent = button.dataset.originalLabel;
      }
    }
  }

  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function renderBaseUrl(url) {
    backendUrlEl.textContent = url || "(unset)";
  }

  async function pingBackend() {
    try {
      const r = await chrome.runtime.sendMessage({ type: "ping" });
      if (!r || !r.ok) return false;
      renderBaseUrl(r.base_url);
      const resp = await fetch(`${r.base_url.replace(/\/api\/v1$/, "")}/api/v1/health`);
      const data = await resp.json();
      return resp.ok && data.status === "ok";
    } catch (err) {
      console.warn("[MailGuard] ping failed", err);
      return false;
    }
  }

  // ---------- Status ----------
  async function refreshStatus() {
    setBusy(testConnectionBtn, true, t("status.testing"));
    try {
      const status = await chrome.runtime.sendMessage({ type: "get-status" });
      renderBaseUrl(status.base_url);

      const reachable = await pingBackend();
      if (!reachable) {
        statusPill.textContent = t("header.backend_down");
        statusPill.className = "mg-pill mg-pill--warn";
        setAuthStatus(
          t("status.unreachable_hint", { url: status.base_url })
        );
      }

      if (status.authenticated) {
        authSection.hidden = true;
        dashSection.hidden = false;
        userName.textContent = status.user?.full_name || status.user?.username || status.user?.email?.split("@")[0] || "user";
        userEmail.textContent = status.user?.email || "";
        userProvider.textContent = `${t("dashboard.role_prefix")}: ${status.user?.role || "user"}`;
        const avatar = status.user?.avatar_url;
        if (avatar) {
          userAvatar.src = avatar;
          userAvatar.style.display = "";
        } else {
          userAvatar.removeAttribute("src");
          userAvatar.style.display = "none";
        }
        if (reachable) {
          statusPill.textContent = t("header.online");
          statusPill.className = "mg-pill mg-pill--online";
          await loadStats();
          await loadRecent();
        }
        await loadGmailStatus();
      } else {
        authSection.hidden = false;
        dashSection.hidden = true;
        statusPill.textContent = reachable ? t("header.ready") : t("header.backend_down");
        statusPill.className = reachable ? "mg-pill mg-pill--online" : "mg-pill mg-pill--warn";
      }
    } catch (err) {
      console.error("[MailGuard] refreshStatus failed", err);
      statusPill.textContent = t("header.error");
      statusPill.className = "mg-pill mg-pill--warn";
      setAuthStatus(t("status.sw_unreachable", { msg: err.message }));
    } finally {
      setBusy(testConnectionBtn, false);
    }
  }

  async function loadStats() {
    try {
      const stats = await chrome.runtime.sendMessage({
        type: "dashboard-stats",
        days: 30,
      });
      if (!stats.ok) throw new Error(stats.error);
      const total = stats.data.total ?? 0;
      statTotal.textContent = total;
      const by = stats.data.by_threat || {};
      const high = (by.high || 0) + (by.critical || 0);
      statRisks.textContent = high;
      const avg = stats.data.avg_risk;
      statAvg.textContent = avg != null ? `${avg.toFixed(1)}` : "0.0";
    } catch (err) {
      console.warn("[MailGuard] loadStats failed", err);
    }
  }

  async function loadRecent() {
    try {
      const data = await chrome.runtime.sendMessage({
        type: "dashboard-recent",
        limit: 5,
      });
      if (!data.ok) throw new Error(data.error);
      const items = data.data?.results || [];
      if (!items.length) {
        recentList.innerHTML = `<li class="mg-list__empty">${escapeHtml(t("empty.recent"))}</li>`;
        return;
      }
      recentList.innerHTML = items
        .map((p) => `
          <li class="mg-list__item">
            <div class="mg-list__item__title">
              <span>${escapeHtml(String(p.predicted_class || "").toUpperCase())}</span>
              <span>${escapeHtml(t("item.risk"))} ${Math.round(p.risk_score || 0)}</span>
            </div>
            <div class="mg-list__item__sub">
              <span class="mg-list__item__pill">${escapeHtml(p.threat_level || "")}</span>
              <span>${new Date(p.created_at).toLocaleString()}</span>
            </div>
          </li>`)
        .join("");
    } catch (err) {
      console.warn("[MailGuard] loadRecent failed", err);
    }
  }

  // ---------- Gmail management ----------
  function formatRelativeTime(iso) {
    if (!iso) return null;
    const then = new Date(iso).getTime();
    if (Number.isNaN(then)) return null;
    const diffMs = Date.now() - then;
    const sec = Math.round(diffMs / 1000);
    const labels = getLocale() === "vi"
      ? { s: "giây", m: "phút", h: "giờ", d: "ngày", ago: "trước" }
      : { s: "s", m: "m", h: "h", d: "d", ago: "ago" };
    if (sec < 60) return getLocale() === "vi"
      ? `vừa xong`
      : `just now`;
    const min = Math.round(sec / 60);
    if (min < 60) return `${min} ${labels.m} ${labels.ago}`;
    const hr = Math.round(min / 60);
    if (hr < 24) return `${hr} ${labels.h} ${labels.ago}`;
    const day = Math.round(hr / 24);
    return `${day} ${labels.d} ${labels.ago}`;
  }

  function setGmailStatus(msg, kind) {
    if (!msg) {
      gmailStatus.hidden = true;
      gmailStatus.textContent = "";
      gmailStatus.className = "mg-popup__status";
      return;
    }
    gmailStatus.hidden = false;
    gmailStatus.textContent = msg;
    gmailStatus.className = kind === "error"
      ? "mg-popup__error"
      : "mg-popup__status";
  }

  function renderGmailConnection(connected, mode, batchSize, lastScanAt, notifyEnabled) {
    if (connected) {
      gmailConnectionPill.textContent = t("gmail.connected");
      gmailConnectionPill.className = "mg-pill mg-pill--online";
      gmailConnectBtn.hidden = true;
      gmailDisconnectBtn.hidden = false;
      gmailScanBtn.disabled = false;
      gmailModeToggle.disabled = false;
      gmailNotifyToggle.disabled = false;
    } else {
      gmailConnectionPill.textContent = t("gmail.not_connected");
      gmailConnectionPill.className = "mg-pill mg-pill--offline";
      gmailConnectBtn.hidden = false;
      gmailDisconnectBtn.hidden = true;
      gmailScanBtn.disabled = true;
      gmailModeToggle.disabled = true;
      gmailNotifyToggle.disabled = true;
    }
    gmailModeToggle.checked = mode === "active";
    gmailNotifyToggle.checked = Boolean(notifyEnabled);
    gmailModeLabel.textContent = connected
      ? (mode === "active"
          ? t("gmail.mode_active", { size: batchSize })
          : t("gmail.mode_passive", { size: batchSize }))
      : t("gmail.connect_to_scan");
    if (lastScanAt) {
      const rel = formatRelativeTime(lastScanAt);
      gmailLastScan.textContent = `${t("gmail.last_scan_prefix")}${rel ? rel + " · " : ""}${new Date(lastScanAt).toLocaleString()}`;
    } else {
      gmailLastScan.textContent = t("empty.scan");
    }
  }

  function renderGmailResults(results) {
    if (!Array.isArray(results) || !results.length) {
      gmailScanList.innerHTML = `<li class="mg-list__empty">${escapeHtml(t("empty.scan"))}</li>`;
      return;
    }
    gmailScanList.innerHTML = results
      .slice(0, 8)
      .map((r, idx) => {
        if (r.error) {
          return `
            <li class="mg-list__item">
              <div class="mg-list__item__title">
                <span class="mg-list__item__sub-text">${escapeHtml(r.subject || t("item.no_subject"))}</span>
                <span class="mg-list__item__pill mg-list__item__pill--high">${escapeHtml(t("item.error_pill"))}</span>
              </div>
              <div class="mg-list__item__sub">
                <span class="mg-list__item__sub-text">${escapeHtml(r.from || "")}</span>
              </div>
              <div class="mg-list__item__error">${escapeHtml(r.error)}</div>
            </li>`;
        }
        const p = r.prediction || {};
        const klass = String(p.predicted_class || "").toLowerCase();
        const level = String(p.threat_level || "").toLowerCase();
        const score = Math.round(p.risk_score || 0);
        // High-risk items get the explanation panel inline so the user
        // sees the AI's reasoning immediately.
        const hasExplanation = (p.highlighted_spans && p.highlighted_spans.length) ||
                               (p.suspicious_urls && p.suspicious_urls.length) ||
                               p.explanation;
        const isHigh = score >= 60 || level === "high" || level === "critical";
        const gmailUrl = buildGmailUrl(r);
        return `
          <li class="mg-list__item ${isHigh ? "mg-list__item--danger" : ""}">
            <div class="mg-list__item__title">
              <span class="mg-list__item__sub-text">${escapeHtml(r.subject || t("item.no_subject"))}</span>
              <span>${escapeHtml(t("item.risk"))} ${score}</span>
            </div>
            <div class="mg-list__item__sub">
              <span class="mg-list__item__pill mg-list__item__pill--${escapeHtml(klass)}">${escapeHtml(p.predicted_class || "")}</span>
              <span class="mg-list__item__pill mg-list__item__pill--${escapeHtml(level)}">${escapeHtml(p.threat_level || "")}</span>
              <span class="mg-list__item__sub-text">${escapeHtml(r.from || "")}</span>
            </div>
            <div class="mg-list__item__actions">
              ${hasExplanation
                ? `<button type="button" class="mg-link-btn" data-toggle-explanation="${idx}">${escapeHtml(t("item.explanation_btn"))}</button>`
                : ""}
              ${r.threadId || r.messageId
                ? `<a class="mg-link-btn" href="${escapeHtml(gmailUrl)}" target="_blank" rel="noreferrer noopener">${escapeHtml(t("item.open_in_gmail"))}</a>`
                : ""}
            </div>
            ${hasExplanation ? renderExplanationPanel(p) : ""}
          </li>`;
      })
      .join("");

    // Wire up the "Why?" toggle buttons.
    gmailScanList.querySelectorAll("[data-toggle-explanation]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const panel = btn.closest(".mg-list__item").querySelector(".mg-explanation");
        if (!panel) return;
        const open = panel.classList.toggle("mg-explanation--open");
        btn.classList.toggle("mg-link-btn--active", open);
      });
    });
  }

  function renderExplanationPanel(p) {
    const spans = Array.isArray(p.highlighted_spans) ? p.highlighted_spans : [];
    const urls = Array.isArray(p.suspicious_urls) ? p.suspicious_urls : [];
    const explanation = p.explanation;
    const explanationText = explanation && typeof explanation === "object"
      ? (explanation.note || explanation.text || JSON.stringify(explanation))
      : explanation;
    return `
      <div class="mg-explanation">
        ${explanationText
          ? `<p class="mg-explanation__summary">${escapeHtml(String(explanationText))}</p>`
          : ""}
        ${spans.length
          ? `<div class="mg-explanation__section">
               <h4>${escapeHtml(t("item.spans_heading"))}</h4>
               <ul class="mg-explanation__list">
                 ${spans
                   .slice(0, 5)
                   .map((s) => `
                     <li>
                       <span class="mg-explanation__quote">"${escapeHtml(s.text || "")}"</span>
                       ${s.reason ? `<span class="mg-explanation__reason">— ${escapeHtml(s.reason)}</span>` : ""}
                     </li>`)
                   .join("")}
               </ul>
             </div>`
          : `<p class="mg-explanation__empty">${escapeHtml(t("item.spans_empty"))}</p>`}
        ${urls.length
          ? `<div class="mg-explanation__section">
               <h4>${escapeHtml(t("item.urls_heading"))}</h4>
               <ul class="mg-explanation__list">
                 ${urls
                   .slice(0, 5)
                   .map((u) => `
                     <li>
                       <span class="mg-explanation__url">${escapeHtml(u.url || "")}</span>
                       ${u.reason ? `<span class="mg-explanation__reason">— ${escapeHtml(u.reason)}</span>` : ""}
                       ${typeof u.score === "number" ? `<span class="mg-explanation__score">(${Math.round(u.score * 100)}%)</span>` : ""}
                     </li>`)
                   .join("")}
               </ul>
             </div>`
          : `<p class="mg-explanation__empty">${escapeHtml(t("item.urls_empty"))}</p>`}
      </div>`;
  }

  /** Build a Gmail URL for opening a specific thread/message. Mirrors the
   * service-worker helper so we can render deep links from the popup.
   */
  function buildGmailUrl({ threadId, messageId }) {
    const base = "https://mail.google.com/mail/u/0/";
    if (threadId) return `${base}#inbox/${threadId}`;
    if (messageId) return `${base}#search/in%3Aanywhere%20rfc822msgid%3A${encodeURIComponent(messageId)}`;
    return base;
  }

  async function loadGmailStatus() {
    try {
      const r = await chrome.runtime.sendMessage({ type: "get-status" });
      if (!r || !r.ok) throw new Error(r?.error || "status failed");
      const g = r.gmail || {};
      renderGmailConnection(
        Boolean(g.connected),
        g.mode || "passive",
        g.batch_size || 25,
        g.last_scan_at,
        g.notify_enabled
      );
      const res = await chrome.runtime.sendMessage({ type: "gmail_get_results" });
      if (res && res.ok) renderGmailResults(res.results || []);
    } catch (err) {
      console.warn("[MailGuard] loadGmailStatus failed", err);
    }
  }

  async function sendMsg(message) {
    const r = await chrome.runtime.sendMessage(message);
    if (!r || !r.ok) {
      throw new Error(r?.error || "request failed");
    }
    return r;
  }

  // ---------- Form handlers ----------
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    setAuthStatus(t("auth.signing_in"));
    const email = emailInput.value.trim();
    const password = passwordInput.value;
    if (!email || !password) {
      setAuthStatus(t("auth.required"));
      return;
    }
    const signInLabel = t("auth.signin");
    const registerLabel = t("auth.register");
    const busyLabel = loginBtnLabel.textContent === registerLabel
      ? t("auth.registering")
      : t("auth.signing_in");
    setBusy(loginBtn, true, busyLabel);
    try {
      const r = await chrome.runtime.sendMessage({
        type: "login",
        payload: { email, password },
      });
      if (!r || !r.ok) {
        throw new Error(r?.error || "Sign-in failed");
      }
      setAuthStatus(t("auth.success"));
      passwordInput.value = "";
      await refreshStatus();
    } catch (err) {
      console.error("[MailGuard] login failed", err);
      const msg = String(err.message || err);
      let humanMsg;
      if (/networkerror|failed.*fetch|load.*network/i.test(msg)) {
        humanMsg = t("auth.network_err", { url: backendUrlEl.textContent });
      } else if (/401/i.test(msg)) {
        humanMsg = t("auth.bad_credentials");
      } else if (/422/i.test(msg)) {
        humanMsg = t("auth.validation_err", { msg: msg.replace(/^422:?\s*/i, "") });
      } else if (/429/i.test(msg)) {
        humanMsg = t("auth.rate_limited");
      } else {
        humanMsg = msg;
      }
      setAuthStatus(`❌ ${humanMsg}`);
    } finally {
      setBusy(loginBtn, false);
    }
  });

  testConnectionBtn.addEventListener("click", async () => {
    setAuthStatus(t("status.testing"));
    const r = await chrome.runtime.sendMessage({ type: "ping" });
    renderBaseUrl(r.base_url);
    const reachable = await pingBackend();
    setAuthStatus(
      reachable
        ? t("status.test_ok", { url: r.base_url })
        : t("status.test_fail", { url: r.base_url })
    );
  });

  logoutBtn.addEventListener("click", async () => {
    setBusy(logoutBtn, true, t("auth.signing_in"));
    try {
      await chrome.runtime.sendMessage({ type: "logout" });
      await refreshStatus();
      setAuthStatus(t("auth.signed_out"));
    } finally {
      setBusy(logoutBtn, false);
    }
  });

  // ---------- Gmail buttons ----------
  gmailConnectBtn.addEventListener("click", async () => {
    setBusy(gmailConnectBtn, true, t("gmail.connecting"));
    setGmailStatus(null);
    try {
      await sendMsg({ type: "gmail_connect" });
      setGmailStatus(`✅ ${t("gmail.connected")}.`, "ok");
      await loadGmailStatus();
    } catch (err) {
      console.error("[MailGuard] gmail_connect failed", err);
      setGmailStatus(`❌ ${err.message}`, "error");
    } finally {
      setBusy(gmailConnectBtn, false);
    }
  });

  gmailDisconnectBtn.addEventListener("click", async () => {
    setBusy(gmailDisconnectBtn, true, t("gmail.disconnecting"));
    setGmailStatus(null);
    try {
      await sendMsg({ type: "gmail_disconnect" });
      setGmailStatus(`${t("gmail.disconnect")} ✓.`, "ok");
      await loadGmailStatus();
    } catch (err) {
      setGmailStatus(`❌ ${err.message}`, "error");
    } finally {
      setBusy(gmailDisconnectBtn, false);
    }
  });

  gmailScanBtn.addEventListener("click", async () => {
    setBusy(gmailScanBtn, true, t("gmail.scanning"));
    setGmailStatus(t("gmail.scanning") + "…");
    try {
      const r = await sendMsg({ type: "gmail_scan_now" });
      const count = (r.results || []).length;
      setGmailStatus(t("gmail.scan_status_ok", { count, s: count === 1 ? "" : "s" }), "ok");
      await loadGmailStatus();
    } catch (err) {
      console.error("[MailGuard] gmail_scan_now failed", err);
      setGmailStatus(`❌ ${err.message}`, "error");
    } finally {
      setBusy(gmailScanBtn, false);
    }
  });

  gmailModeToggle.addEventListener("change", async () => {
    const mode = gmailModeToggle.checked ? "active" : "passive";
    setGmailStatus(null);
    try {
      await sendMsg({ type: "gmail_set_mode", mode, batch_size: 25 });
      setGmailStatus(t("gmail.mode_set", { mode }), "ok");
      await loadGmailStatus();
    } catch (err) {
      gmailModeToggle.checked = !gmailModeToggle.checked;
      setGmailStatus(`❌ ${err.message}`, "error");
    }
  });

  gmailNotifyToggle.addEventListener("change", async () => {
    const enabled = gmailNotifyToggle.checked;
    setGmailStatus(null);
    try {
      await sendMsg({ type: "gmail_set_notify", enabled });
      setGmailStatus(
        enabled ? `✅ ${t("gmail.notif_enabled_msg")}` : "",
        "ok"
      );
    } catch (err) {
      gmailNotifyToggle.checked = !gmailNotifyToggle.checked;
      setGmailStatus(`❌ ${err.message}`, "error");
    }
  });

  openOptions.addEventListener("click", (e) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
  });

  await refreshStatus();
})();