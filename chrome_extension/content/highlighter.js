/**
 * MailGuard-AI — Highlighter.
 *
 * Receives a prediction result from the backend and:
 *  - Renders a banner above the email body with the verdict
 *  - Highlights suspicious spans (keywords + risky URLs) inside the body
 *  - Attaches a tooltip on each highlighted span
 */

const Highlighter = {
  BANNER_ID: "__mailguard_banner__",

  /**
   * Apply the highlighter to the currently-open email.
   * @param {object} prediction - the result returned by /api/v1/predictions
   */
  apply(prediction) {
    if (!prediction) return;
    this.renderBanner(prediction);
    this.highlightSpans(prediction.highlighted_spans || []);
  },

  renderBanner(prediction) {
    document.getElementById(this.BANNER_ID)?.remove();

    const emailContainer = window.GmailScraper?.findOpenEmailContainer();
    if (!emailContainer) {
      // If the email container is no longer present in the DOM (e.g. user went back to inbox),
      // do not render the banner.
      return;
    }

    const banner = document.createElement("div");
    banner.id = this.BANNER_ID;
    banner.className = `mg-banner mg-banner--${prediction.threat_level}`;
    const palette = this.paletteFor(prediction.threat_level);
    banner.style.background = palette.bg;
    banner.style.color = palette.fg;
    banner.style.border = `1px solid ${palette.border}`;

    const clsLabel = (prediction.predicted_class || "").toUpperCase();
    const risk = Math.round(prediction.risk_score || 0);
    banner.innerHTML = `
      <div class="mg-banner__title">
        <strong>MailGuard-AI</strong>
        <span class="mg-banner__pill">${clsLabel}</span>
        <span class="mg-banner__risk">Risk ${risk}/100</span>
      </div>
      <div class="mg-banner__summary">${this.escapeHtml(
        prediction.explanation?.summary || "No summary available.",
      )}</div>
      <div class="mg-banner__actions">
        <button class="mg-banner__btn" data-mg-action="correct">This is correct</button>
        <button class="mg-banner__btn" data-mg-action="incorrect">Report mistake</button>
      </div>
    `;

    emailContainer.parentElement.prepend(banner);

    banner.querySelectorAll("[data-mg-action]").forEach((btn) => {
      btn.addEventListener("click", () =>
        this.onFeedback(prediction, btn.dataset.mgAction === "correct"),
      );
    });
  },

  async onFeedback(prediction, isCorrect) {
    try {
      const api = window.MailGuardAPI;
      if (!api.isAuthenticated()) {
        window.MailGuardUI?.toast(
          "Please log in via the extension popup to submit feedback.",
          "warning",
        );
        return;
      }
      await api.sendFeedback({
        prediction_id: prediction.id,
        is_correct: isCorrect,
        comment: null,
      });
      window.MailGuardUI?.toast("Thanks for your feedback!", "success");
    } catch (err) {
      window.MailGuardUI?.toast(`Feedback failed: ${err.message}`, "danger");
    }
  },

  highlightSpans(spans) {
    const container = window.GmailScraper?.findOpenEmailContainer();
    if (!container || !spans.length) return;
    // Simple version: walk text nodes and wrap matched substrings.
    // For complex Gmail DOM, we recommend layering a Shadow DOM in production.
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
    const nodes = [];
    let n;
    while ((n = walker.nextNode())) nodes.push(n);

    nodes.forEach((node) => {
      const text = node.nodeValue;
      if (!text || text.length < 5) return;
      const matches = [];
      for (const span of spans) {
        if (span.start == null || span.end == null) continue;
        // Gmail DOM has been heavily modified; use substring search
        const substring = text.substring(span.start, span.end);
        if (substring) {
          matches.push({ start: span.start, end: span.end, span });
        }
      }
      if (!matches.length) return;
      const fragment = document.createDocumentFragment();
      let cursor = 0;
      matches.sort((a, b) => a.start - b.start);
      for (const m of matches) {
        if (m.start > cursor) {
          fragment.appendChild(document.createTextNode(text.slice(cursor, m.start)));
        }
        const mark = document.createElement("mark");
        mark.className = `mg-mark mg-mark--${m.span.category}`;
        mark.style.background = m.span.category === "url" ? "#fde2e1" : "#fff3bf";
        mark.style.padding = "0 2px";
        mark.style.borderRadius = "2px";
        mark.textContent = text.slice(m.start, m.end);
        mark.title = m.span.reason || m.span.text;
        fragment.appendChild(mark);
        cursor = m.end;
      }
      if (cursor < text.length) {
        fragment.appendChild(document.createTextNode(text.slice(cursor)));
      }
      node.parentNode.replaceChild(fragment, node);
    });
  },

  paletteFor(level) {
    const palettes = {
      low: { bg: "#ecfdf5", fg: "#065f46", border: "#a7f3d0" },
      medium: { bg: "#fffbeb", fg: "#92400e", border: "#fcd34d" },
      high: { bg: "#fff7ed", fg: "#9a3412", border: "#fdba74" },
      critical: { bg: "#fef2f2", fg: "#991b1b", border: "#fca5a5" },
    };
    return palettes[level] || palettes.low;
  },

  escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[c]);
  },
};

if (typeof window !== "undefined") {
  window.MailGuardHighlighter = Highlighter;
}