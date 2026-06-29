/**
 * MailGuard-AI — Popup logic.
 * Connects to the API singleton and renders dashboard / login form.
 */

(async function initPopup() {
  const api = window.MailGuardAPI || (await import("../lib/api.js")).api;
  await api.loadConfig();

  const authSection = document.getElementById("auth-section");
  const dashSection = document.getElementById("dashboard-section");
  const statusPill = document.getElementById("status-pill");
  const userName = document.getElementById("user-name");
  const statTotal = document.getElementById("stat-total");
  const statRisks = document.getElementById("stat-risks");
  const statAvg = document.getElementById("stat-avg");
  const recentList = document.getElementById("recent-list");
  const errorMsg = document.getElementById("error-msg");
  const loginForm = document.getElementById("login-form");
  const openOptions = document.getElementById("open-options");
  const openRegister = document.getElementById("open-register");
  const logoutBtn = document.getElementById("logout-btn");

  function setError(msg) {
    if (!msg) {
      errorMsg.hidden = true;
      errorMsg.textContent = "";
      return;
    }
    errorMsg.hidden = false;
    errorMsg.textContent = msg;
  }

  async function refreshStatus() {
    const status = await chrome.runtime.sendMessage({ type: "get-status" });
    if (!status.ok) {
      statusPill.textContent = "Error";
      return;
    }
    statusPill.textContent = status.authenticated ? "Online" : "Offline";
    statusPill.className = `mg-pill ${
      status.authenticated ? "mg-pill--online" : "mg-pill--offline"
    }`;
    if (status.authenticated) {
      authSection.hidden = true;
      dashSection.hidden = false;
      userName.textContent =
        status.user?.full_name || status.user?.username || "user";
      await loadStats();
      await loadRecent();
    } else {
      authSection.hidden = false;
      dashSection.hidden = true;
    }
  }

  async function loadStats() {
    try {
      const stats = await api.getStats(30);
      statTotal.textContent = stats.total ?? 0;
      const high =
        (stats.by_threat?.high || 0) + (stats.by_threat?.critical || 0);
      statRisks.textContent = high;
      statAvg.textContent =
        stats.avg_risk != null ? `${stats.avg_risk.toFixed(1)}` : "0.0";
    } catch (err) {
      setError(`Failed to load stats: ${err.message}`);
    }
  }

  async function loadRecent() {
    try {
      const data = await api.getRecent(5);
      const items = data.results || [];
      if (!items.length) {
        recentList.innerHTML = '<li class="mg-list__empty">No predictions yet.</li>';
        return;
      }
      recentList.innerHTML = items
        .map(
          (p) => `
          <li class="mg-list__item">
            <div class="mg-list__item__title">
              <span>${escapeHtml(p.predicted_class.toUpperCase())}</span>
              <span>Risk ${Math.round(p.risk_score)}</span>
            </div>
            <div class="mg-list__item__sub">
              <span class="mg-list__item__pill mg-list__item__pill--${p.predicted_class}">
                ${p.threat_level}
              </span>
              <span>${new Date(p.created_at).toLocaleString()}</span>
            </div>
          </li>`,
        )
        .join("");
    } catch (err) {
      setError(`Failed to load recent predictions: ${err.message}`);
    }
  }

  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    setError("");
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    try {
      await chrome.runtime.sendMessage({
        type: "login",
        payload: { email, password },
      });
      await refreshStatus();
    } catch (err) {
      setError(err.message || "Login failed");
    }
  });

  openRegister.addEventListener("click", (e) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
  });

  openOptions.addEventListener("click", () => chrome.runtime.openOptionsPage());

  logoutBtn.addEventListener("click", async () => {
    await chrome.runtime.sendMessage({ type: "logout" });
    await refreshStatus();
  });

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
    );
  }

  await refreshStatus();
})();