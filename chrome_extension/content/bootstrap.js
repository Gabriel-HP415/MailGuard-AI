/**
 * MailGuard-AI — Content bootstrap.
 *
 * This file is intentionally last in the content_scripts list. It:
 *   1. Loads the API + UI config from chrome.storage.
 *   2. Watches Gmail for opened emails.
 *   3. Sends each new email to the backend and applies the highlighter.
 *   4. Caches results per-message so we don't spam the API.
 */

(async function bootstrap() {
  console.log("[MailGuard] Content script bootstrap started!");
  const api = window.MailGuardAPI;
  const ui = window.MailGuardUI;
  const scraper = window.GmailScraper;
  const highlighter = window.MailGuardHighlighter;
  console.log("[MailGuard] Checked globals:", { api: !!api, ui: !!ui, scraper: !!scraper, highlighter: !!highlighter });
  if (!api || !scraper || !highlighter) return;

  await api.loadConfig();
  console.log("[MailGuard] Config loaded:", { baseUrl: api.baseUrl, hasToken: !!api.token });

  const cache = new Map();

  async function analyze(payload) {
    console.log("[MailGuard] Analyzing payload:", payload);
    const key = `${payload.sender}|${payload.subject}|${(payload.body_text || "").slice(0, 80)}`;
    if (cache.has(key)) {
      console.log("[MailGuard] Returning cached result for key:", key);
      highlighter.apply(cache.get(key));
      return;
    }
    console.log("[MailGuard] Checking if authenticated:", api.isAuthenticated());
    if (!api.isAuthenticated()) {
      console.warn("[MailGuard] Not authenticated! Showing warning toast.");
      ui?.toast("MailGuard-AI: please log in via the popup.", "warning", 5000);
      return;
    }
    try {
      console.log("[MailGuard] Sending prediction request to:", api.baseUrl);
      const result = await api.predict(payload, { includeExplanation: true });
      console.log("[MailGuard] Prediction result received:", result);
      cache.set(key, result);
      highlighter.apply(result);
    } catch (err) {
      console.error("[MailGuard] predict failed:", err);
      ui?.toast(`MailGuard-AI error: ${err.message}`, "danger", 5000);
    }
  }

  scraper.watch((payload) => {
    console.log("[MailGuard] Scraper detected email open event.");
    analyze(payload);
  });
})();