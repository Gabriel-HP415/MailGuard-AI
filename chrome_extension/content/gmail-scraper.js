/**
 * MailGuard-AI — Gmail DOM scraper.
 *
 * Extracts:
 *  - sender email + display name
 *  - subject
 *  - plain-text body (collapsed / expanded views)
 *  - links found in the body
 *
 * The scraper is resilient: Gmail updates its DOM frequently, so selectors
 * fall back to multiple strategies and the cache avoids duplicate work.
 */

const GmailScraper = {
  /** @type {Map<string, object>} */
  _cache: new Map(),

  /**
   * Find the currently-open email in the Gmail thread view.
   * Returns null if no email is opened.
   */
  findOpenEmailContainer() {
    // Strategy 1: classic expanded message
    let el = document.querySelector("div.a3s.aiL");
    if (el) return el;

    // Strategy 2: Gmail 2024+ layout
    el = document.querySelector("div[role='main'] div.a3s");
    if (el) return el;

    // Strategy 3: Anything that looks like a message body
    el = document.querySelector("[data-message-id] div.a3s");
    return el;
  },

  /**
   * Get the subject of the currently-open thread.
   */
  getSubject() {
    const subjEl =
      document.querySelector("h2.hP") ||
      document.querySelector("div[role='main'] h2") ||
      document.querySelector("span[data-thread-subject]");
    return subjEl ? subjEl.innerText.trim() : "";
  },

  /**
   * Get the sender of the currently-open message.
   * Gmail usually renders this as "Name <email@domain>".
   */
  getSender() {
    const spans = document.querySelectorAll("div[role='main'] span[email], div[role='main'] .gD");
    for (const s of spans) {
      const email = s.getAttribute("email");
      const name = s.innerText.trim();
      if (email) {
        return name && name.includes(email) ? name : `${name} <${email}>`;
      }
      if (name && name.includes("@")) return name;
    }
    // Fallback
    const fallback = document.querySelector("span.g2");
    return fallback ? fallback.innerText.trim() : "";
  },

  /**
   * Extract a clean plain-text body from the open email.
   * Strips quoted replies, signatures, and Gmail's UI noise.
   */
  getBodyText() {
    const container = this.findOpenEmailContainer();
    if (!container) return "";
    let text = container.innerText || "";
    text = text
      .split("\n")
      .map((line) => line.trim())
      .filter(
        (line) =>
          line &&
          !line.startsWith(">") &&
          !/^On .+ wrote:$/.test(line) &&
          !/^--\s*$/.test(line),
      )
      .join("\n");
    return text.trim();
  },

  /**
   * Extract links from the open email body.
   */
  getLinks() {
    const container = this.findOpenEmailContainer();
    if (!container) return [];
    const urls = new Set();
    container.querySelectorAll("a[href]").forEach((a) => {
      const href = a.getAttribute("href");
      if (!href) return;
      // Gmail wraps real URLs in redirects starting with https://www.google.com/url
      const m = href.match(/[?&]q=([^&]+)/);
      if (m) {
        try {
          urls.add(decodeURIComponent(m[1]));
          return;
        } catch (err) {
          // ignore
        }
      }
      if (href.startsWith("http")) urls.add(href);
    });
    return Array.from(urls);
  },

  /**
   * Build the email payload ready to send to the backend.
   * @param {string} gmailId
   */
  buildPayload(gmailId = null) {
    const sender = this.getSender();
    const senderEmail = (sender.match(/<([^>]+)>/) || [, sender])[1] || sender;
    const domain = senderEmail.includes("@") ? senderEmail.split("@")[1] : null;
    return {
      gmail_id: gmailId,
      sender: senderEmail,
      sender_domain: domain,
      subject: this.getSubject(),
      body_text: this.getBodyText(),
      links: this.getLinks(),
    };
  },

  /**
   * Watch the Gmail DOM and emit a `mailguard:email-opened` event whenever
   * a different email is opened by the user.
   */
  watch(onOpen) {
    let lastKey = "";
    const observer = new MutationObserver(() => {
      const payload = this.buildPayload();
      const key = `${payload.sender}|${payload.subject}|${(payload.body_text || "").slice(0, 80)}`;
      if (key && key !== lastKey && payload.body_text) {
        lastKey = key;
        try {
          onOpen(payload);
        } catch (err) {
          console.error("[MailGuard] onOpen error:", err);
        }
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
    return observer;
  },
};

if (typeof window !== "undefined") {
  window.GmailScraper = GmailScraper;
}