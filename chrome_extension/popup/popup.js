/**
 * MailGuard-AI — Popup logic.
 *
 * Clean implementation focused on the email/password (universal) sign-in
 * flow. Gmail OAuth remains as a disabled stub — it'll be re-enabled when
 * the module-based SW is wired back up.
 *
 * Flow:
 *   1. On open: ask SW for `get-status` to discover current base URL + auth state.
 *   2. Always show the backend URL in the status strip (debug-friendly).
 *   3. Sign-in / register: send `login` or `register` to SW (classic).
 *   4. SW performs fetch and returns a plain {ok, data} | {ok: false, error}.
 *
 * Why ping first: if the backend URL is misconfigured, we want the user to
 * see "Backend unreachable" instead of "Wrong password".
 */

(async function initPopup() {
  const authStatus = document.getElementById("auth-status");
  const statusPill = document.getElementById("status-pill");
  const backendUrlEl = document.getElementById("backend-url");
  const testConnectionBtn = document.getElementById("test-connection-btn");

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

  // ---------- helpers ----------
  function setAuthStatus(msg) {
    authStatus.textContent = msg || "";
  }

  function setBusy(button, busy, busyLabel) {
    if (!button) return;
    if (busy) {
      button.disabled = true;
      button.dataset.originalLabel = button.dataset.originalLabel || button.textContent;
      button.textContent = busyLabel || "Please wait…";
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
      // Issue a real /health fetch to surface obvious misconfig
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
    setBusy(testConnectionBtn, true, "Testing…");
    try {
      const status = await chrome.runtime.sendMessage({ type: "get-status" });
      renderBaseUrl(status.base_url);

      // Run a network probe independently so we can show "unreachable"
      // even when get-status claims the URL is fine.
      const reachable = await pingBackend();
      if (!reachable) {
        statusPill.textContent = "Backend down";
        statusPill.className = "mg-pill mg-pill--warn";
        setAuthStatus(
          `⚠ Cannot reach ${status.base_url}. ` +
          `Run \`docker compose -f docker-compose.dev.yml up -d\` and reload.`
        );
      }

      if (status.authenticated) {
        authSection.hidden = true;
        dashSection.hidden = false;
        userName.textContent = status.user?.full_name || status.user?.username || status.user?.email?.split("@")[0] || "user";
        userEmail.textContent = status.user?.email || "";
        userProvider.textContent = `Signed in as ${status.user?.role || "user"}`;
        const avatar = status.user?.avatar_url;
        if (avatar) {
          userAvatar.src = avatar;
          userAvatar.style.display = "";
        } else {
          userAvatar.removeAttribute("src");
          userAvatar.style.display = "none";
        }
        if (reachable) {
          statusPill.textContent = "Online";
          statusPill.className = "mg-pill mg-pill--online";
          await loadStats();
          await loadRecent();
        }
      } else {
        authSection.hidden = false;
        dashSection.hidden = true;
        statusPill.textContent = reachable ? "Ready" : "Backend down";
        statusPill.className = reachable ? "mg-pill mg-pill--online" : "mg-pill mg-pill--warn";
      }
    } catch (err) {
      console.error("[MailGuard] refreshStatus failed", err);
      statusPill.textContent = "Error";
      statusPill.className = "mg-pill mg-pill--warn";
      setAuthStatus(`Cannot contact service worker: ${err.message}`);
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
        recentList.innerHTML = '<li class="mg-list__empty">No predictions yet.</li>';
        return;
      }
      recentList.innerHTML = items
        .map((p) => `
          <li class="mg-list__item">
            <div class="mg-list__item__title">
              <span>${escapeHtml(String(p.predicted_class || "")).toUpperCase()}</span>
              <span>Risk ${Math.round(p.risk_score || 0)}</span>
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

  // ---------- Form handlers ----------
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    setAuthStatus("Signing in…");
    const email = emailInput.value.trim();
    const password = passwordInput.value;
    if (!email || !password) {
      setAuthStatus("Email and password are required.");
      return;
    }
    setBusy(loginBtn, true, loginBtnLabel.textContent === "Register" ? "Creating…" : "Signing in…");
    try {
      const r = await chrome.runtime.sendMessage({
        type: "login",
        payload: { email, password },
      });
      if (!r || !r.ok) {
        throw new Error(r?.error || "Sign-in failed");
      }
      setAuthStatus("Success — fetching dashboard…");
      passwordInput.value = "";
      await refreshStatus();
    } catch (err) {
      console.error("[MailGuard] login failed", err);
      const msg = String(err.message || err);
      let humanMsg;
      if (/networkerror|failed.*fetch|load.*network/i.test(msg)) {
        humanMsg = `Cannot reach backend. Check "${backendUrlEl.textContent}" is running.`;
      } else if (/401/i.test(msg)) {
        humanMsg = `Wrong email or password (or this account doesn't exist).`;
      } else if (/422/i.test(msg)) {
        humanMsg = `Validation error: ${msg.replace(/^422:?\s*/i, "")}`;
      } else if (/429/i.test(msg)) {
        humanMsg = `Too many sign-in attempts. Wait a minute and try again.`;
      } else {
        humanMsg = msg;
      }
      setAuthStatus(`❌ ${humanMsg}`);
    } finally {
      setBusy(loginBtn, false);
    }
  });

  testConnectionBtn.addEventListener("click", async () => {
    setAuthStatus("Testing connection…");
    const r = await chrome.runtime.sendMessage({ type: "ping" });
    renderBaseUrl(r.base_url);
    const reachable = await pingBackend();
    setAuthStatus(
      reachable
        ? `✅ Backend is reachable at ${r.base_url}`
        : `❌ Cannot reach ${r.base_url}. Is docker container running?`
    );
  });

  logoutBtn.addEventListener("click", async () => {
    setBusy(logoutBtn, true, "Signing out…");
    try {
      await chrome.runtime.sendMessage({ type: "logout" });
      await refreshStatus();
      setAuthStatus("Signed out.");
    } finally {
      setBusy(logoutBtn, false);
    }
  });

  openOptions.addEventListener("click", (e) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
  });

  // Re-render the dashboard every time the popup opens so the data is fresh.
  await refreshStatus();
})();
