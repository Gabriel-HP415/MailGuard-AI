/**
 * MailGuard-AI — Popup logic.
 * Connects to the API singleton and renders dashboard / login form.
 *
 * Supports two sign-in methods:
 *   - "Sign in with Google"  → chrome.identity OAuth → Firebase ID token →
 *                              POST /api/v1/auth/firebase/login → backend JWT
 *   - email/password         → POST /api/v1/auth/login (legacy / dev only)
 */

(async function initPopup() {
  const api = window.MailGuardAPI || (await import("../lib/api.js")).api;
  await api.loadConfig();
  const firebaseAuth = await import("../lib/firebase.js");

  const authSection = document.getElementById("auth-section");
  const dashSection = document.getElementById("dashboard-section");
  const statusPill = document.getElementById("status-pill");
  const userName = document.getElementById("user-name");
  const userEmail = document.getElementById("user-email");
  const userAvatar = document.getElementById("user-avatar");
  const statTotal = document.getElementById("stat-total");
  const statRisks = document.getElementById("stat-risks");
  const statAvg = document.getElementById("stat-avg");
  const recentList = document.getElementById("recent-list");
  const errorMsg = document.getElementById("error-msg");
  const loginForm = document.getElementById("login-form");
  const openOptions = document.getElementById("open-options");
  const openRegister = document.getElementById("open-register");
  const logoutBtn = document.getElementById("logout-btn");
  const googleSignInBtn = document.getElementById("google-signin-btn");

  function setError(msg) {
    if (!msg) {
      errorMsg.hidden = true;
      errorMsg.textContent = "";
      return;
    }
    errorMsg.hidden = false;
    errorMsg.textContent = msg;
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
      const profile = await firebaseAuth.getCurrentUser();
      const name =
        status.user?.full_name || status.user?.username || profile.firebase_display_name || "user";
      userName.textContent = name;
      userEmail.textContent = status.user?.email || profile.firebase_email || "";
      const photoUrl = profile.firebase_photo_url || status.user?.avatar_url || "";
      if (photoUrl) {
        userAvatar.src = photoUrl;
        userAvatar.style.display = "";
      } else {
        userAvatar.removeAttribute("src");
        userAvatar.style.display = "none";
      }
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
    setBusy(loginForm.querySelector("button"), true, "Signing in…");
    try {
      await chrome.runtime.sendMessage({
        type: "login",
        payload: { email, password },
      });
      await refreshStatus();
    } catch (err) {
      setError(err.message || "Login failed");
    } finally {
      setBusy(loginForm.querySelector("button"), false);
    }
  });

  googleSignInBtn.addEventListener("click", async () => {
    setError("");
    setBusy(googleSignInBtn, true, "Opening Google sign-in…");
    try {
      const profile = await firebaseAuth.signInWithGoogle();
      // Notify background service worker so it can update its in-memory state.
      await chrome.runtime.sendMessage({ type: "firebase_signed_in", payload: profile });
      await refreshStatus();
    } catch (err) {
      console.error("Google sign-in failed", err);
      setError(err.message || "Google sign-in failed");
    } finally {
      setBusy(googleSignInBtn, false);
    }
  });

  openRegister.addEventListener("click", (e) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
  });

  openOptions.addEventListener("click", () => chrome.runtime.openOptionsPage());

  logoutBtn.addEventListener("click", async () => {
    setBusy(logoutBtn, true, "Signing out…");
    try {
      await chrome.runtime.sendMessage({ type: "logout" });
      await firebaseAuth.signOut();
      await refreshStatus();
    } finally {
      setBusy(logoutBtn, false);
    }
  });

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
    );
  }

  await refreshStatus();
})();