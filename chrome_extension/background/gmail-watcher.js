/**
 * MailGuard-AI — Gmail inbox watcher.
 *
 * Periodically polls the Gmail inbox via `lib/gmail.js` and forwards every new
 * email to the backend MailGuard AI for classification. The watcher's cadence
 * is driven by `chrome.alarms`, which survives service-worker termination.
 *
 * Modes:
 *   - "passive" (default): classify in real-time when user opens an email.
 *     The Gmail content-script handles highlighting directly.
 *   - "active" : proactively scan the latest N messages every 5 minutes,
 *     even if the user never opens them. Useful for "scam folder" pre-tagging.
 *
 * In both modes the watcher writes results back to `chrome.storage.local` so
 * the popup/options UI can render a dashboard without an extra round-trip.
 */

import { fetchDecodedInbox, getGmailAccessToken } from "./gmail.js";

const ALARM_NAME = "mailguard-gmail-poll";
const POLL_INTERVAL_MINUTES = 5;
const SCAN_BATCH_SIZE = 25;
export const STORAGE_KEYS = {
  LAST_SCAN_AT: "mg_gmail_last_scan_at",
  SCAN_RESULTS: "mg_gmail_scan_results",
  MODE: "mg_gmail_mode",
};

/** Boot the watcher on extension install / startup. */
export function installGmailWatcher(api) {
  try {
    chrome.alarms.create(ALARM_NAME, {
      periodInMinutes: POLL_INTERVAL_MINUTES,
    });
  } catch (err) {
    console.warn("[MailGuard] alarms.create failed:", err);
  }

  // We do NOT install chrome.runtime.onMessage here — that listener is owned
  // by service-worker.js to avoid the "Maximum number of registrations
  // reached" error that killed the SW before. The service-worker.js forwards
  // `gmail_scan_now` and `gmail_get_last_scan` messages to runScan().
  chrome.alarms.onAlarm.addListener(async (alarm) => {
    if (alarm.name !== ALARM_NAME) return;
    await runScan(api).catch((err) =>
      console.warn("[MailGuard] scan alarm failed:", err.message),
    );
  });
}

/** Run one scan pass. Called by the alarm or by `gmail_scan_now`. */
export async function runScan(api) {
  const token = await getGmailAccessToken({ interactive: false });
  if (!token) {
    throw new Error("Gmail access token not granted");
  }

  const emails = await fetchDecodedInbox({ maxResults: SCAN_BATCH_SIZE });
  if (!emails.length) return [];

  const results = [];
  // Sequential to stay under Gmail rate limits (~250 quota units / user / sec).
  for (const email of emails) {
    try {
      const payload = {
        email: {
          sender: email.from,
          subject: email.subject,
          body_text: (email.body_text || "").slice(0, 8000),
          body_html: null,
          links: [],
          attachments: email.attachments,
          received_at: email.date || null,
        },
        model_version: null,
        include_explanation: true,
      };
      const prediction = await api.predict(payload);
      results.push({
        messageId: email.id,
        threadId: email.threadId,
        subject: email.subject,
        from: email.from,
        snippet: email.snippet,
        prediction: {
          predicted_class: prediction.predicted_class,
          class_index: prediction.class_index,
          confidence: prediction.confidence,
          risk_score: prediction.risk_score,
          threat_level: prediction.threat_level,
          suspicious_urls: prediction.suspicious_urls,
        },
        scanned_at: new Date().toISOString(),
      });
    } catch (err) {
      console.warn(
        `[MailGuard] prediction failed for ${email.id}:`,
        err.message,
      );
      results.push({
        messageId: email.id,
        subject: email.subject,
        from: email.from,
        error: err.message,
        scanned_at: new Date().toISOString(),
      });
    }
  }

  await chrome.storage.local.set({
    [STORAGE_KEYS.LAST_SCAN_AT]: new Date().toISOString(),
    [STORAGE_KEYS.SCAN_RESULTS]: results,
  });
  return results;
}