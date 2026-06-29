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
  const api = window.MailGuardAPI;
  const ui = window.MailGuardUI;
  const scraper = window.GmailScraper;
  const highlighter = window.MailGuardHighlighter;
  if (!api || !scraper || !highlighter) return;

  await api.loadConfig();

  const cache = new Map();

  async function analyze(payload) {
    const key = `${payload.sender}|${payload.subject}|${(payload.body_text || "").slice(0, 80)}`;
    if (cache.has(key)) {
      highlighter.apply(cache.get(key));
      return;
    }
    if (!api.isAuthenticated()) {
      ui?.toast("MailGuard-AI: please log in via the popup.", "warning", 5000);
      return;
    }
    try {
      const result = await api.predict(payload, { includeExplanation: true });
      cache.set(key, result);
      highlighter.apply(result);
    } catch (err) {
      console.error("[MailGuard] predict failed:", err);
      ui?.toast(`MailGuard-AI error: ${err.message}`, "danger", 5000);
    }
  }

  scraper.watch((payload) => analyze(payload));
})();