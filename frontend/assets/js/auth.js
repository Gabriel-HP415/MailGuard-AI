/* Login page logic. */
(function () {
  const form = document.getElementById("login-form");
  const errorMsg = document.getElementById("error-msg");
  const submitBtn = document.getElementById("submit-btn");
  const submitLabel = document.getElementById("submit-label");
  const baseUrlInput = document.getElementById("base-url-input");
  const settingsPanel = document.getElementById("settings-panel");
  const settingsLink = document.getElementById("settings-link");

  baseUrlInput.value = api.baseUrl;

  settingsLink.addEventListener("click", (e) => {
    e.preventDefault();
    settingsPanel.hidden = !settingsPanel.hidden;
  });

  document.getElementById("save-base-url").addEventListener("click", () => {
    const url = baseUrlInput.value.trim() || api.baseUrl;
    api.saveConfig({ baseUrl: url });
    UI.toast("Backend URL saved", "success");
  });

  function setError(msg) {
    if (!msg) {
      errorMsg.hidden = true;
      errorMsg.textContent = "";
      return;
    }
    errorMsg.hidden = false;
    errorMsg.textContent = msg;
  }

  function setLoading(loading) {
    submitBtn.disabled = loading;
    submitLabel.textContent = loading ? "Signing in…" : "Sign in";
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const email = document.getElementById("email").value.trim();
      const password = document.getElementById("password").value;
      await api.login({ email, password });
      const next = new URLSearchParams(window.location.search).get("next") || "/dashboard.html";
      window.location.href = next;
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  });

  // Already logged in? Go straight to dashboard.
  if (api.isAuthenticated()) {
    window.location.href = "/dashboard.html";
  }
})();