/**
 * MailGuard-AI — Gmail API client.
 *
 * Provides a thin wrapper over the Gmail REST API v1 that the Chrome
 * extension uses to read the user's mailbox when they sign in with Google.
 *
 * Auth model:
 *   - We call `chrome.identity.getAuthToken({ interactive: true })` to obtain
 *     a short-lived OAuth access token (default ~1 hour).
 *   - The token is automatically refreshed by Chrome's identity layer.
 *   - All requests go to https://gmail.googleapis.com/gmail/v1/users/me/*.
 *
 * Why this exists:
 *   - `chrome.identity` only gives us identity tokens. To READ the mailbox we
 *     need Gmail-API scopes (`gmail.readonly` / `gmail.modify`).
 *   - The existing `firebase.js` / `oauth.js` flow exchanges a Firebase ID
 *     token for a backend JWT; this module complements it by giving the
 *     background worker direct Gmail access.
 */

const GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me";

/** Pending scopes the extension would like to request. Must match manifest. */
const REQUIRED_SCOPES = [
  "https://www.googleapis.com/auth/gmail.readonly",
  "https://www.googleapis.com/auth/gmail.modify",
];

let _cachedToken = null;
let _cachedTokenExpiresAt = 0;

/** Get a valid OAuth access token for the Gmail API.
 *
 * `chrome.identity.getAuthToken` caches tokens automatically. We additionally
 * track the expiry ourselves so we can pre-emptively refresh before a long
 * batch job starts (avoids one 401 mid-scan).
 */
export async function getGmailAccessToken({ interactive = true } = {}) {
  const now = Date.now();
  if (_cachedToken && now < _cachedTokenExpiresAt - 30_000) {
    return _cachedToken;
  }

  const token = await new Promise((resolve, reject) => {
    chrome.identity.getAuthToken({ interactive }, (result) => {
      if (chrome.runtime.lastError || !result) {
        reject(new Error(chrome.runtime.lastError?.message || "No token"));
        return;
      }
      resolve(result);
    });
  });

  _cachedToken = token;
  // Chrome tokens last 60 minutes; we refresh at 50 to avoid edge cases.
  _cachedTokenExpiresAt = now + 50 * 60 * 1000;
  return token;
}

/** Revoke the current token (used on sign-out). */
export async function revokeGmailAccess() {
  if (!_cachedToken) return;
  return new Promise((resolve) => {
    chrome.identity.removeCachedAuthToken({ token: _cachedToken }, () => {
      _cachedToken = null;
      _cachedTokenExpiresAt = 0;
      // Also fetch with `revoke=true` so Google server-side revokes it.
      fetch(`https://accounts.google.com/o/oauth2/revoke?token=${_cachedToken}`)
        .catch(() => {})
        .finally(resolve);
    });
  });
}

/** Low-level GET against the Gmail API with automatic token refresh. */
async function gmailFetch(path, { method = "GET", params } = {}) {
  let token = await getGmailAccessToken({ interactive: false });
  let url = `${GMAIL_API_BASE}${path}`;
  if (params) {
    const qs = new URLSearchParams(params).toString();
    if (qs) url += `?${qs}`;
  }

  let resp = await fetch(url, {
    method,
    headers: { Authorization: `Bearer ${token}` },
  });

  // 401 → force a fresh interactive token and retry once.
  if (resp.status === 401) {
    _cachedToken = null;
    _cachedTokenExpiresAt = 0;
    token = await getGmailAccessToken({ interactive: true });
    resp = await fetch(url, {
      method,
      headers: { Authorization: `Bearer ${token}` },
    });
  }

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Gmail API ${resp.status}: ${text.slice(0, 300)}`);
  }
  return resp.json();
}

/* ------------------------------------------------------------------
   Listing & fetching messages
   ------------------------------------------------------------------ */

/** Return the most recent N message stubs from the inbox.
 *
 * @param {number} maxResults  How many to fetch (max 500 per call).
 * @param {string} query       Optional Gmail search query (e.g. "is:unread").
 */
export async function listInbox({ maxResults = 50, query = "in:inbox" } = {}) {
  const data = await gmailFetch("/messages", {
    params: { maxResults, q: query },
  });
  return data.messages || [];
}

/** Fetch a single message in full and decode its payload into a flat object. */
export async function getMessage(messageId, { format = "full" } = {}) {
  return gmailFetch(`/messages/${encodeURIComponent(messageId)}`, {
    params: { format },
  });
}

/** Walk a Gmail payload tree and pull out subject/from/body text.
 *
 * Gmail messages are RFC 3501 / MIME trees. We don't ship a full parser
 * here — only the fields the AI needs:
 *   - subject
 *   - from (header)
 *   - to (header)
 *   - body_text (the first text/plain part, decoded)
 *   - body_html (the first text/html part, decoded)
 *   - attachments (filenames only)
 */
export function extractEmailContent(msg) {
  const headers = msg?.payload?.headers || [];
  const header = (name) =>
    headers.find((h) => h.name.toLowerCase() === name.toLowerCase())?.value || "";

  const subject = header("Subject");
  const from = header("From");
  const to = header("To");
  const date = header("Date");

  let bodyText = "";
  let bodyHtml = "";
  const attachments = [];

  function walk(part) {
    if (!part) return;
    const mime = (part.mimeType || "").toLowerCase();

    if (part.filename) {
      attachments.push({
        name: part.filename,
        mimeType: mime,
        size: part.body?.size || 0,
        attachmentId: part.body?.attachmentId || null,
      });
    }

    if (mime === "text/plain" && !bodyText && part.body?.data) {
      bodyText = decodeBase64Url(part.body.data);
    } else if (mime === "text/html" && !bodyHtml && part.body?.data) {
      bodyHtml = decodeBase64Url(part.body.data);
    }

    if (Array.isArray(part.parts)) {
      for (const child of part.parts) walk(child);
    }
  }

  walk(msg.payload);

  return {
    id: msg.id,
    threadId: msg.threadId,
    subject,
    from,
    to,
    date,
    snippet: msg.snippet || "",
    body_text: bodyText,
    body_html: bodyHtml,
    attachments,
    labelIds: msg.labelIds || [],
  };
}

/** Gmail uses base64url (no padding). Decode safely across browsers. */
function decodeBase64Url(data) {
  if (!data) return "";
  // Replace URL-safe chars, re-pad, then atob.
  const normalized = data.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
  try {
    // atob returns a "binary string"; encodeURIComponent+escape round-trips
    // it into proper UTF-8 (Gmail bodies often contain non-ASCII).
    const binary = atob(padded);
    return decodeURIComponent(
      Array.from(binary)
        .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join(""),
    );
  } catch (err) {
    console.warn("[MailGuard] Gmail body decode failed", err);
    return "";
  }
}

/* ------------------------------------------------------------------
   High-level helper used by the background watcher
   ------------------------------------------------------------------ */

/** Fetch the inbox + decode every message into a payload the backend can consume. */
export async function fetchDecodedInbox({ maxResults = 25 } = {}) {
  const stubs = await listInbox({ maxResults });
  const results = [];
  for (const stub of stubs) {
    try {
      const full = await getMessage(stub.id);
      results.push(extractEmailContent(full));
    } catch (err) {
      console.warn(`[MailGuard] skipping message ${stub.id}:`, err.message);
    }
  }
  return results;
}

/** Returns true if the Gmail API is currently authorised (non-interactive check). */
export async function isAuthorised() {
  try {
    await getGmailAccessToken({ interactive: false });
    return true;
  } catch {
    return false;
  }
}