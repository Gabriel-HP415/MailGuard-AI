/**
 * MailGuard-AI — Options page logic.
 * Handles login, registration, base URL, whitelist/blacklist management.
 */

(async function initOptions() {
  if (!window.MailGuardAPI) {
    await import("../lib/api.js");
  }
  const api = window.MailGuardAPI;
  await api.loadConfig();
  const firebaseAuth = await import("../lib/firebase.js");

  const authPill = document.getElementById("auth-pill");
  const baseUrlInput = document.getElementById("base-url");
  const emailInput = document.getElementById("email");
  const passwordInput = document.getElementById("password");
  const authStatus = document.getElementById("auth-status");
  const authForm = document.getElementById("auth-form");
  const logoutBtn = document.getElementById("logout-btn");

  const profileCard = document.getElementById("profile-card");
  const profileAvatar = document.getElementById("profile-avatar");
  const profileName = document.getElementById("profile-name");
  const profileEmail = document.getElementById("profile-email");
  const profileProvider = document.getElementById("profile-provider");
  const googleSignInBtn = document.getElementById("google-signin-btn");
  const firebaseSignOutBtn = document.getElementById("firebase-signout-btn");

  const whitelistForm = document.getElementById("whitelist-form");
  const blacklistForm = document.getElementById("blacklist-form");
  const whitelistList = document.getElementById("whitelist-list");
  const blacklistList = document.getElementById("blacklist-list");
  const serviceStatus = document.getElementById("service-status");

  const gmailPill = document.getElementById("gmail-options-pill");
  const gmailLast = document.getElementById("gmail-options-last");
  const gmailConnectBtn = document.getElementById("gmail-options-connect");
  const gmailDisconnectBtn = document.getElementById("gmail-options-disconnect");
  const gmailScanBtn = document.getElementById("gmail-options-scan");
  const gmailBatchInput = document.getElementById("gmail-options-batch");
  const gmailThresholdInput = document.getElementById("gmail-options-threshold");
  const gmailThresholdValue = document.getElementById("gmail-options-threshold-value");
  const gmailNotifyEnabledInput = document.getElementById("gmail-options-notify");
  const gmailStatus = document.getElementById("gmail-options-status");
  const gmailModeRadios = document.querySelectorAll('input[name="gmail-mode"]');

  // Init UI from storage
  baseUrlInput.value = api.baseUrl || "";

  function setAuthStatus(text, ok = false) {
    authStatus.textContent = text;
    authStatus.style.color = ok ? "var(--success)" : "var(--danger)";
  }

  async function refreshProfile() {
    const profile = await firebaseAuth.getCurrentUser();
    const signedIn = await firebaseAuth.isSignedIn();
    if (!signedIn) {
      profileCard.hidden = true;
      return;
    }
    profileCard.hidden = false;
    profileName.textContent = profile.firebase_display_name || "Google user";
    profileEmail.textContent = profile.firebase_email || "";
    profileProvider.textContent = "Signed in with Google";
    if (profile.firebase_photo_url) {
      profileAvatar.src = profile.firebase_photo_url;
      profileAvatar.style.display = "";
    } else {
      profileAvatar.removeAttribute("src");
      profileAvatar.style.display = "none";
    }
  }

  async function refreshAuth() {
    const status = await chrome.runtime.sendMessage({ type: "get-status" });
    if (!status.ok) {
      authPill.textContent = "Error";
      authPill.className = "mg-pill mg-pill--offline";
      return;
    }
    authPill.textContent = status.authenticated ? "Online" : "Offline";
    authPill.className = `mg-pill ${
      status.authenticated ? "mg-pill--online" : "mg-pill--offline"
    }`;
    if (status.user) {
      setAuthStatus(`Signed in as ${status.user.email}`, true);
    } else {
      setAuthStatus("Not signed in.");
    }
  }

  // Save base URL on blur
  baseUrlInput.addEventListener("change", async () => {
    const url = baseUrlInput.value.trim() || "https://mailguard-ai-y0nh.onrender.com/api/v1";
    await api.saveConfig({ baseUrl: url });
    setAuthStatus(`Backend URL saved: ${url}`, true);
  });

  authForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    setAuthStatus("Working…");
    const action = e.submitter?.value || "login";
    const payload = {
      email: emailInput.value.trim(),
      password: passwordInput.value,
    };
    if (action === "register") {
      payload.username = payload.email.split("@")[0];
      payload.full_name = payload.username;
    }
    try {
      const result = await chrome.runtime.sendMessage({
        type: action,
        payload,
      });
      if (!result.ok) {
        // Map common errors to actionable text
        const err = String(result.error || "");
        let msg = err;
        if (/401/i.test(err)) {
          msg = "Wrong email or password (or account doesn't exist). Click Register to create one.";
        } else if (/422/i.test(err)) {
          msg = `Validation error: ${err.replace(/^422:?\s*/i, "")}`;
        } else if (/network|failed.*fetch|load.*network/i.test(err)) {
          msg = `Cannot reach backend at ${api.baseUrl}. Is docker container running?`;
        } else if (/429/i.test(err)) {
          msg = "Too many attempts. Wait a minute.";
        }
        throw new Error(msg);
      }
      await refreshAuth();
      await Promise.all([loadWhitelist(), loadBlacklist(), loadServiceStatus()]);
      passwordInput.value = "";
      setAuthStatus(`Signed in as ${payload.email}`, true);
    } catch (err) {
      setAuthStatus(`Error: ${err.message}`);
    }
  });

  googleSignInBtn.addEventListener("click", async () => {
    setAuthStatus("Opening Google sign-in…");
    googleSignInBtn.disabled = true;
    try {
      const profile = await firebaseAuth.signInWithGoogle();
      await chrome.runtime.sendMessage({ type: "firebase_signed_in", payload: profile });
      await refreshAuth();
      await refreshProfile();
      await Promise.all([loadWhitelist(), loadBlacklist(), loadServiceStatus()]);
      setAuthStatus(`Signed in as ${profile.email}`, true);
    } catch (err) {
      setAuthStatus(`Error: ${err.message}`);
    } finally {
      googleSignInBtn.disabled = false;
    }
  });

  firebaseSignOutBtn.addEventListener("click", async () => {
    await chrome.runtime.sendMessage({ type: "logout" });
    await firebaseAuth.signOut();
    await refreshAuth();
    await refreshProfile();
    whitelistList.innerHTML = '<li class="mg-options__empty">Sign in to manage lists.</li>';
    blacklistList.innerHTML = '<li class="mg-options__empty">Sign in to manage lists.</li>';
    setAuthStatus("Signed out.");
  });

  logoutBtn.addEventListener("click", async () => {
    await chrome.runtime.sendMessage({ type: "logout" });
    await refreshAuth();
    await refreshProfile();
    whitelistList.innerHTML = '<li class="mg-options__empty">Sign in to manage lists.</li>';
    blacklistList.innerHTML = '<li class="mg-options__empty">Sign in to manage lists.</li>';
  });

  // -------- Whitelist --------
  whitelistForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const sender = document.getElementById("wl-sender").value.trim();
    const note = document.getElementById("wl-note").value.trim();
    try {
      await api.addWhitelist({ sender, note: note || null });
      whitelistForm.reset();
      await loadWhitelist();
    } catch (err) {
      alert(`Add failed: ${err.message}`);
    }
  });

  async function loadWhitelist() {
    if (!api.isAuthenticated()) {
      whitelistList.innerHTML =
        '<li class="mg-options__empty">Sign in to manage lists.</li>';
      return;
    }
    try {
      const items = await api.getWhitelist();
      if (!items.length) {
        whitelistList.innerHTML =
          '<li class="mg-options__empty">No entries yet.</li>';
        return;
      }
      whitelistList.innerHTML = items
        .map(
          (i) => `
          <li>
            <div>
              <strong>${escapeHtml(i.sender)}</strong>
              ${i.note ? `<div style="font-size:11px;color:#64748b">${escapeHtml(i.note)}</div>` : ""}
            </div>
            <button data-id="${i.id}" data-action="whitelist">Remove</button>
          </li>`,
        )
        .join("");
    } catch (err) {
      whitelistList.innerHTML = `<li class="mg-options__empty">Failed to load: ${err.message}</li>`;
    }
  }

  whitelistList.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action='whitelist']");
    if (!btn) return;
    const id = parseInt(btn.dataset.id, 10);
    try {
      await api.removeWhitelist(id);
      await loadWhitelist();
    } catch (err) {
      alert(`Remove failed: ${err.message}`);
    }
  });

  // -------- Blacklist --------
  blacklistForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const sender = document.getElementById("bl-sender").value.trim();
    const reason = document.getElementById("bl-reason").value.trim();
    try {
      await api.addBlacklist({ sender, reason: reason || null });
      blacklistForm.reset();
      await loadBlacklist();
    } catch (err) {
      alert(`Add failed: ${err.message}`);
    }
  });

  async function loadBlacklist() {
    if (!api.isAuthenticated()) {
      blacklistList.innerHTML =
        '<li class="mg-options__empty">Sign in to manage lists.</li>';
      return;
    }
    try {
      const items = await api.getBlacklist();
      if (!items.length) {
        blacklistList.innerHTML =
          '<li class="mg-options__empty">No entries yet.</li>';
        return;
      }
      blacklistList.innerHTML = items
        .map(
          (i) => `
          <li>
            <div>
              <strong>${escapeHtml(i.sender)}</strong>
              ${i.reason ? `<div style="font-size:11px;color:#64748b">${escapeHtml(i.reason)}</div>` : ""}
            </div>
            <button data-id="${i.id}" data-action="blacklist">Remove</button>
          </li>`,
        )
        .join("");
    } catch (err) {
      blacklistList.innerHTML = `<li class="mg-options__empty">Failed to load: ${err.message}</li>`;
    }
  }

  blacklistList.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action='blacklist']");
    if (!btn) return;
    const id = parseInt(btn.dataset.id, 10);
    try {
      await api.removeBlacklist(id);
      await loadBlacklist();
    } catch (err) {
      alert(`Remove failed: ${err.message}`);
    }
  });

  // -------- Gmail options --------
  function setGmailOptsStatus(text, ok = false) {
    gmailStatus.textContent = text || "";
    gmailStatus.style.color = ok ? "var(--success)" : "var(--danger)";
  }

  function renderGmailState({ connected, mode, batch_size, last_scan_at, notify_enabled, notify_threshold }) {
    if (connected) {
      gmailPill.textContent = "Connected";
      gmailPill.className = "mg-pill mg-pill--online";
      gmailConnectBtn.hidden = true;
      gmailDisconnectBtn.hidden = false;
      gmailScanBtn.disabled = false;
    } else {
      gmailPill.textContent = "Not connected";
      gmailPill.className = "mg-pill mg-pill--offline";
      gmailConnectBtn.hidden = false;
      gmailDisconnectBtn.hidden = true;
      gmailScanBtn.disabled = true;
    }
    for (const r of gmailModeRadios) r.checked = (r.value === (mode || "passive"));
    gmailBatchInput.value = batch_size || 25;
    if (gmailNotifyEnabledInput) gmailNotifyEnabledInput.checked = Boolean(notify_enabled);
    if (gmailThresholdInput) {
      gmailThresholdInput.value = notify_threshold || 60;
    }
    if (gmailThresholdValue) {
      gmailThresholdValue.textContent = String(notify_threshold || 60);
    }
    gmailLast.textContent = last_scan_at
      ? `Last scan: ${new Date(last_scan_at).toLocaleString()}`
      : "No scans yet.";
  }

  async function refreshGmail() {
    try {
      const r = await chrome.runtime.sendMessage({ type: "get-status" });
      if (!r || !r.ok) throw new Error(r?.error || "status failed");
      renderGmailState(r.gmail || {});
    } catch (err) {
      gmailPill.textContent = "Error";
      gmailPill.className = "mg-pill mg-pill--offline";
      setGmailOptsStatus(err.message);
    }
  }

  async function persistGmailConfig() {
    const mode = document.querySelector('input[name="gmail-mode"]:checked')?.value || "passive";
    const batch = Math.min(Math.max(Number(gmailBatchInput.value) || 25, 1), 100);
    try {
      await chrome.runtime.sendMessage({
        type: "gmail_set_mode",
        mode,
        batch_size: batch,
      });
      setGmailOptsStatus(`Saved: mode=${mode}, batch=${batch}`, true);
      await refreshGmail();
    } catch (err) {
      setGmailOptsStatus(err.message);
    }
  }

  gmailConnectBtn.addEventListener("click", async () => {
    setGmailOptsStatus("Connecting…");
    try {
      await chrome.runtime.sendMessage({ type: "gmail_connect" });
      setGmailOptsStatus("Connected.", true);
      await refreshGmail();
    } catch (err) {
      setGmailOptsStatus(err.message);
    }
  });

  gmailDisconnectBtn.addEventListener("click", async () => {
    setGmailOptsStatus("Disconnecting…");
    try {
      await chrome.runtime.sendMessage({ type: "gmail_disconnect" });
      setGmailOptsStatus("Disconnected.", true);
      await refreshGmail();
    } catch (err) {
      setGmailOptsStatus(err.message);
    }
  });

  gmailScanBtn.addEventListener("click", async () => {
    setGmailOptsStatus("Scanning…");
    gmailScanBtn.disabled = true;
    try {
      const r = await chrome.runtime.sendMessage({ type: "gmail_scan_now" });
      const count = (r.results || []).length;
      setGmailOptsStatus(`Scanned ${count} message${count === 1 ? "" : "s"}.`, true);
      await refreshGmail();
    } catch (err) {
      setGmailOptsStatus(err.message);
    } finally {
      gmailScanBtn.disabled = false;
    }
  });

  for (const r of gmailModeRadios) r.addEventListener("change", persistGmailConfig);
  gmailBatchInput.addEventListener("change", persistGmailConfig);

  // Threshold slider should update the live label and persist with the
  // current enabled state.
  gmailThresholdInput?.addEventListener("input", () => {
    if (gmailThresholdValue) {
      gmailThresholdValue.textContent = String(gmailThresholdInput.value);
    }
  });
  gmailThresholdInput?.addEventListener("change", async () => {
    try {
      const threshold = Math.min(Math.max(Number(gmailThresholdInput.value) || 60, 1), 100);
      const enabled = Boolean(gmailNotifyEnabledInput?.checked);
      await chrome.runtime.sendMessage({
        type: "gmail_set_notify",
        enabled,
        threshold,
      });
      setGmailOptsStatus(`Saved: notify=${enabled}, threshold=${threshold}`, true);
    } catch (err) {
      setGmailOptsStatus(err.message);
    }
  });
  gmailNotifyEnabledInput?.addEventListener("change", async () => {
    try {
      const enabled = Boolean(gmailNotifyEnabledInput.checked);
      const threshold = Math.min(Math.max(Number(gmailThresholdInput?.value) || 60, 1), 100);
      await chrome.runtime.sendMessage({
        type: "gmail_set_notify",
        enabled,
        threshold,
      });
      setGmailOptsStatus(`Saved: notify=${enabled}, threshold=${threshold}`, true);
    } catch (err) {
      gmailNotifyEnabledInput.checked = !gmailNotifyEnabledInput.checked;
      setGmailOptsStatus(err.message);
    }
  });

  // -------- Service status --------
  async function loadServiceStatus() {
    try {
      const health = await api.getAIHealth();
      serviceStatus.innerHTML = `<pre style="white-space:pre-wrap;font-family:monospace;font-size:11.5px;">${JSON.stringify(
        health,
        null,
        2,
      )}</pre>`;
    } catch (err) {
      serviceStatus.textContent = `Could not reach AI service: ${err.message}`;
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
    );
  }

  await refreshAuth();
  await refreshProfile();
  await refreshGmail();
  await loadWhitelist();
  await loadBlacklist();
  await loadServiceStatus();
})();