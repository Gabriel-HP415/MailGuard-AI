/**
 * MailGuard-AI — Popup logic.
 *
 * Default sign-in is email/password (universal, no OAuth client needed).
 * Google sign-in is hidden under an <details> "Advanced" panel and only works
 * if the project has a Chrome Extension OAuth client configured.
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
  const userProvider = document.getElementById("user-provider");
  const statTotal = document.getElementById("stat-total");
  const statRisks = document.getElementById("stat-risks");
  const statAvg = document.getElementById("stat-avg");
  const recentList = document.getElementById("recent-list");
  const errorMsg = document.getElementById("error-msg");
  const loginForm = document.getElementById("login-form");
  const loginBtnLabel = document.getElementById("login-btn-label");
  const openOptions = document.getElementById("open-options");
  const openRegister = document.getElementById("open-register");
  const logoutBtn = document.getElementById("logout-btn");
  const googleSignInBtn = document.getElementById("google-signin-btn");

  // Two modes for the email/password form: "sign-in" vs "register".
  let formMode = "sign-in";

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

  function switchToRegister() {
    formMode = "register";
    loginBtnLabel.textContent = "Create account";
    const passwordInput = document.getElementById("password");
    if (passwordInput) passwordInput.setAttribute("autocomplete", "new-password");
    setError("");
  }

  function switchToSignIn() {
    formMode = "sign-in";
    loginBtnLabel.textContent = "Sign in";
    const passwordInput = document.getElementById("password");
    if (passwordInput) passwordInput.setAttribute("autocomplete", "current-password");
    setError("");
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
      const provider = profile?.auth_provider || "google";
      const name =
        status.user?.full_name ||
        status.user?.username ||
        profile?.firebase_display_name ||
        "user";
      userName.textContent = name;
      userEmail.textContent = status.user?.email || profile?.firebase_email || "";
      if (userProvider) {
        userProvider.textContent =
          provider === "google" ? "Signed in with Google" : "Signed in with email";
      }
      const photoUrl = profile?.firebase_photo_url || status.user?.avatar_url || "";
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

  // ---- Email / password: sign-in or register ----
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    setError("");
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    const submitBtn = loginForm.querySelector("button");
    setBusy(submitBtn, true, formMode === "register" ? "Creating account…" : "Signing in…");

    try {
      if (formMode === "register") {
        const username = email.split("@")[0];
        // /auth/register returns TokenResponse, so we're already signed in.
        await chrome.runtime.sendMessage({
          type: "register",
          payload: { email, password, username, full_name: username },
        });
      } else {
        await chrome.runtime.sendMessage({
          type: "login",
          payload: { email, password },
        });
      }
      await refreshStatus();
      document.getElementById("password").value = "";
      switchToSignIn();
    } catch (err) {
      setError(formatAuthError(err));
    } finally {
      setBusy(submitBtn, false);
    }
  });

  googleSignInBtn.addEventListener("click", async () => {
    setError("");
    setBusy(googleSignInBtn, true, "Opening Google sign-in…");
    try {
      const profile = await firebaseAuth.signInWithGoogle();
      await chrome.runtime.sendMessage({
        type: "firebase_signed_in",
        payload: profile,
      });
      await refreshStatus();
    } catch (err) {
      console.error("[MailGuard] Google sign-in failed", err);
      setError(formatAuthError(err));
    } finally {
      setBusy(googleSignInBtn, false);
    }
  });

  openRegister.addEventListener("click", (e) => {
    e.preventDefault();
    switchToRegister();
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

  function formatAuthError(err) {
    const msg = String(err && err.message ? err.message : err || "Unknown error");
    const lower = msg.toLowerCase();
    if (/cancel|approve|denied/i.test(msg)) {
      return "Google sign-in was cancelled.";
    }
    if (lower.includes("invalid_grant")) {
      return "Sign-in link expired. Please sign in again with email/password.";
    }
    if (/invalid.*oauth.*client|unregistered|oauth.*client.*id/i.test(msg)) {
      return "OAuth client misconfigured. Sign in with email/password below instead.";
    }
    if (/firebase refused/i.test(msg)) {
      return "Google sign-in failed. Use email/password below (recommended).";
    }
    if (/redirect_uri_mismatch/i.test(msg)) {
      return "Google sign-in needs a Chrome Extension OAuth client. Email/password below works without it.";
    }
    if (/401|unauthor/i.test(msg)) {
      return "Wrong email or password, or your account doesn't exist yet. Click Register above to create one.";
    }
    if (/409|already exists|taken/i.test(msg)) {
      return "An account with that email already exists. Click 'Sign in' instead.";
    }
    if (/422|validation|password.*short|password.*8/i.test(msg)) {
      return "Password must be at least 8 characters.";
    }
    if (/network|failed to fetch/i.test(msg)) {
      return "Network error talking to the backend. Check your internet connection and the Backend URL in settings.";
    }
    if (/backend|503|500/i.test(msg)) {
      // Try to surface a more useful hint from common SQLAlchemy / MySQL errors.
      const hint =
        /Unknown column|1054/.test(msg)
          ? "Database schema is out of date. Run the Alembic migration on the backend: `alembic upgrade head`."
          : /doesn't exist|1146/.test(msg)
            ? "A required database table is missing. Run `alembic upgrade head` on the backend."
          : /Access denied|1045/.test(msg)
            ? "Database credentials are wrong. Check DB_* environment variables."
            : /pymysql|operationalerror|connection refused|2003/i.test(msg)
              ? "Cannot reach the database. Check DB_HOST / DB_PORT."
              : null;
      return (
        (hint ? hint + " (" : "Backend rejected the request. (") +
        msg.replace(/^Backend login failed \(.*?\): /, "").slice(0, 240) +
        ")"
      );
    }
    return msg;
  }

  await refreshStatus();
})();
