/**
 * Test: Native notification flow (chrome.notifications).
 *
 * Replicates notifyDanger() + bumpRiskCount() from the service worker to verify:
 *   1. LOW-risk email  -> no notification, no badge bump
 *   2. HIGH-risk email -> OS notification fired, badge bumped
 *   3. MEDIUM-risk     -> no notification, no badge bump
 *   4. CRITICAL email  -> OS notification fired, badge bumped
 *   5. 5-minute throttle prevents spam notifications
 *   6. Badge still bumps during cooldown (even without notification)
 *
 * Usage:
 *   node scripts/test_notification_flow.cjs
 *
 * Prerequisites:
 *   - backend at http://127.0.0.1:8003/api/v1
 *   - admin@mailguard.ai / ChangeMe123! seeded
 */

// ─── Chrome stub ─────────────────────────────────────────────────────────────

const notifLog = [];   // [{id, opts}]
const storage = new Map();
let badgeText = "";

const chrome = {
  storage: {
    local: {
      get: (k) => {
        const keys = typeof k === "string" ? [k] : k;
        const out = {};
        for (const key of keys) out[key] = storage.get(key);
        return Promise.resolve(out);
      },
      set: (o) => { for (const k in o) storage.set(k, o[k]); return Promise.resolve(); },
      remove: (k) => { (Array.isArray(k) ? k : [k]).forEach((x) => storage.delete(x)); return Promise.resolve(); },
    },
  },
  notifications: {
    create: (id, opts) => {
      notifLog.push({ id, opts });
      return Promise.resolve(id);
    },
    clear: () => Promise.resolve(),
    onClicked: { addListener: () => {} },
    onClosed: { addListener: () => {} },
  },
  alarms: {
    get: () => Promise.resolve(null),
    create: () => {},
    clear: () => Promise.resolve(),
    onAlarm: { addListener: () => {} },
  },
  action: {
    setBadgeText: ({ text }) => { badgeText = text; },
    setBadgeBackgroundColor: () => {},
  },
  tabs: { create: () => {} },
  runtime: {
    lastError: null,
    onMessage: { addListener: () => {} },
    onInstalled: { addListener: () => {} },
    onStartup: { addListener: () => {} },
  },
  identity: { getAuthToken: () => Promise.reject(new Error("mock: no token")) },
};

// ─── Storage keys ─────────────────────────────────────────────────────────────

const STORAGE_KEYS = {
  GMAIL_NOTIFY: "mg_gmail_notify",
  GMAIL_NOTIFY_THRESHOLD: "mg_gmail_notify_threshold",
  GMAIL_NOTIFY_COOLDOWN_UNTIL: "mg_gmail_notify_cooldown_until",
  GMAIL_RISK_COUNT: "mg_gmail_risk_count",
  BASE_URL: "mg_base_url",
};
const DEFAULT_THRESHOLD = 60;

// ─── Core SW logic (mirrored from service-worker.classic.js) ────────────────

async function notifyDanger({ subject, from, riskScore, threatLevel, messageId, threadId }) {
  const cfg = await chrome.storage.local.get([
    STORAGE_KEYS.GMAIL_NOTIFY,
    STORAGE_KEYS.GMAIL_NOTIFY_THRESHOLD,
    STORAGE_KEYS.GMAIL_NOTIFY_COOLDOWN_UNTIL,
  ]);
  if (!cfg[STORAGE_KEYS.GMAIL_NOTIFY]) return;
  const threshold = Number(cfg[STORAGE_KEYS.GMAIL_NOTIFY_THRESHOLD]) || DEFAULT_THRESHOLD;
  if ((riskScore || 0) < threshold) return;
  if (!chrome.notifications || !chrome.notifications.create) return;

  const id = `mailguard-danger-${messageId || "x"}-${Date.now()}`;
  await chrome.storage.local.set({ [`mailguard_notif_${id}`]: { threadId, messageId, at: Date.now() } });

  const cooldownUntil = Number(cfg[STORAGE_KEYS.GMAIL_NOTIFY_COOLDOWN_UNTIL]) || 0;
  if (Date.now() < cooldownUntil) {
    // Throttle: skip OS notification, but still bump badge for the popup.
    await bumpRiskCount();
    return;
  }

  await chrome.notifications.create(id, {
    type: "basic",
    iconUrl: "icons/icon128.png",
    title: "⚠️ Email nguy hiểm — MailGuard-AI",
    message: `Phát hiện email rủi ro cao (${Math.round(riskScore)}/100)`,
    contextMessage: `${from || "(không rõ người gửi)"} — ${subject || "(không có tiêu đề)"}`,
    priority: 2,
    requireInteraction: true,
  });

  // Set 5-minute cooldown
  await chrome.storage.local.set({
    [STORAGE_KEYS.GMAIL_NOTIFY_COOLDOWN_UNTIL]: Date.now() + 5 * 60 * 1000,
  });
  await bumpRiskCount();
}

async function bumpRiskCount() {
  const stored = await chrome.storage.local.get([STORAGE_KEYS.GMAIL_RISK_COUNT]);
  const next = Number(stored[STORAGE_KEYS.GMAIL_RISK_COUNT] || 0) + 1;
  await chrome.storage.local.set({ [STORAGE_KEYS.GMAIL_RISK_COUNT]: next });
  if (chrome.action && chrome.action.setBadgeText) {
    await chrome.action.setBadgeText({ text: next > 99 ? "99+" : String(next) });
  }
}

// ─── HTTP helpers ─────────────────────────────────────────────────────────────

function httpPost(url, body, headers = {}) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const opts = {
      hostname: u.hostname, port: u.port || 80,
      path: u.pathname + u.search, method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
    };
    const req = require("http").request(opts, (res) => {
      let data = "";
      res.on("data", c => data += c);
      res.on("end", () => {
        try { resolve({ status: res.statusCode, data: JSON.parse(data) }); }
        catch { resolve({ status: res.statusCode, data }); }
      });
    });
    req.on("error", reject);
    req.write(JSON.stringify(body));
    req.end();
  });
}

// ─── Backend predict ───────────────────────────────────────────────────────

async function mockPredictEmail(email, baseUrl, token) {
  const body = {
    email: {
      sender: email.from,
      sender_domain: email.from.split("@")[1]?.split(/[<>\s]/)[0] || "",
      recipient: "user@gmail.com",
      subject: email.subject,
      body_text: email.body_text.slice(0, 8000),
      body_html: null,
      links: [],
      attachments: [],
      received_at: email.date,
    },
    model_version: null,
    include_explanation: true,
  };
  try {
    const resp = await httpPost(`${baseUrl}/predictions`, body, { Authorization: `Bearer ${token}` });
    return resp.data;
  } catch (e) {
    return { error: e.message };
  }
}

// ─── Mock Gmail inbox ──────────────────────────────────────────────────────

const MOCK_INBOX = [
  // [0] LOW risk (5/100) → no notification, no badge bump
  { id: "msg001", threadId: "thr001", from: "team@company.com",
    subject: "Weekly engineering report",
    body_text: "Hi team, please find the weekly report attached. Best, Engineering.",
    date: new Date().toISOString() },
  // [1] HIGH risk scam (85/100) → notification, badge bump
  { id: "msg002", threadId: "thr002", from: "security@paypa1.com <paypa1.com>",
    subject: "URGENT: Verify your account now or it will be suspended",
    body_text: "Dear Customer, Your account has been temporarily suspended due to suspicious activity. " +
      "Click http://paypa1-secure.com/verify to confirm your identity and avoid permanent suspension. " +
      "You must verify within 24 hours or your account will be permanently closed. " +
      "Enter your credit card number to confirm ownership.",
    date: new Date().toISOString() },
  // [2] MEDIUM risk (21/100) → no notification, no badge bump
  { id: "msg003", threadId: "thr003", from: "promo@dealshop.click",
    subject: "80% off everything — limited time only!",
    body_text: "Buy now at dealshop.click! Amazing 80% discount on all items!",
    date: new Date().toISOString() },
  // [3] CRITICAL risk (93/100) → notification, badge bump
  { id: "msg004", threadId: "thr004", from: "noreply@bankoffake.net",
    subject: "Your account has been LOCKED — verify immediately",
    body_text: "We detected a suspicious login attempt from an unknown IP address (Russia). " +
      "Your bank account has been temporarily LOCKED. " +
      "Click https://bankoffake.net/secure-login to unlock and verify your SSN and account password. " +
      "Failure to comply within 12 hours will result in permanent account suspension.",
    date: new Date().toISOString() },
];

// ─── Main ────────────────────────────────────────────────────────────────────

async function main() {
  console.log("=".repeat(60));
  console.log("MAILGUARD-AI: Notification Flow Test");
  console.log("=".repeat(60));
  let passed = 0, failed = 0;

  // Step 1: Login
  console.log("\n[STEP 1] Login");
  const resp = await httpPost(
    "http://127.0.0.1:8003/api/v1/auth/login",
    { email: "admin@mailguard.ai", password: "ChangeMe123!" }
  );
  if (resp.status !== 200) { console.log(`  FAIL ${resp.status}`); process.exit(1); }
  const token = resp.data.access_token;
  console.log(`  OK token=${token.slice(0, 20)}...`);
  passed++;

  // Step 2: Init storage
  console.log("\n[STEP 2] Enable notification (notify=true, threshold=60)");
  await chrome.storage.local.set({
    [STORAGE_KEYS.GMAIL_NOTIFY]: true,
    [STORAGE_KEYS.GMAIL_NOTIFY_THRESHOLD]: 60,
    [STORAGE_KEYS.GMAIL_NOTIFY_COOLDOWN_UNTIL]: 0,
    [STORAGE_KEYS.GMAIL_RISK_COUNT]: 0,
  });
  console.log("  OK");
  passed++;

  // Step 3: Test each email (fresh cooldown for each)
  console.log("\n[STEP 3] Test LOW / HIGH / MEDIUM / CRITICAL emails");
  const baseUrl = "http://127.0.0.1:8003/api/v1";
  const expectations = [
    { idx: 0, expectNotify: false, expectBump: false, desc: "LOW risk (5)   — < threshold" },
    { idx: 1, expectNotify: true,  expectBump: true,  desc: "HIGH risk (85) — >= threshold, notify" },
    { idx: 2, expectNotify: false, expectBump: false, desc: "MEDIUM risk (21)— < threshold" },
    { idx: 3, expectNotify: true,  expectBump: true,  desc: "CRITICAL risk (93)— >= threshold, notify" },
  ];

  for (const { idx, expectNotify, expectBump, desc } of expectations) {
    // Reset cooldown for each — each email gets a fresh scan window
    await chrome.storage.local.set({ [STORAGE_KEYS.GMAIL_NOTIFY_COOLDOWN_UNTIL]: 0 });

    const email = MOCK_INBOX[idx];
    const prevNotif = notifLog.length;
    const prevBadge = storage.get(STORAGE_KEYS.GMAIL_RISK_COUNT) || 0;

    const pred = await mockPredictEmail(email, baseUrl, token);
    if (pred.error) {
      console.log(`  ❌ ${desc}: ${pred.error}`);
      failed++;
      continue;
    }

    await notifyDanger({
      subject: email.subject, from: email.from,
      riskScore: pred.risk_score || 0,
      threatLevel: pred.threat_level || "?",
      messageId: email.id, threadId: email.threadId,
    });

    const notified = notifLog.length > prevNotif;
    const bumped = (storage.get(STORAGE_KEYS.GMAIL_RISK_COUNT) || 0) > prevBadge;

    console.log(`\n  [${desc}] risk=${pred.risk_score} class=${pred.predicted_class}`);
    if (pred.explanation?.matched_signals?.length) {
      console.log(`    signals: ${pred.explanation.matched_signals.slice(0, 5).join(", ")}`);
    }

    if (notified === expectNotify) { console.log(`    ✅ notif=${notified}`); passed++; }
    else { console.log(`    ❌ notif=${notified} expected ${expectNotify}`); failed++; }
    if (bumped === expectBump) { console.log(`    ✅ badge_bump=${bumped}`); passed++; }
    else { console.log(`    ❌ badge_bump=${bumped} expected ${expectBump}`); failed++; }
  }

  // Step 4: Badge total — only emails >= threshold bump it (emails 1 and 3)
  console.log("\n[STEP 4] Badge counter total");
  const riskCount = storage.get(STORAGE_KEYS.GMAIL_RISK_COUNT);
  console.log(`  risk_count=${riskCount} badge="${badgeText}"`);
  if (riskCount === 2 && badgeText === "2") {
    console.log("  ✅ Correct (2 emails >= threshold: HIGH + CRITICAL)");
    passed++;
  } else {
    console.log(`  ❌ Expected 2`);
    failed++;
  }

  // Step 5: Cooldown active after last notification
  console.log("\n[STEP 5] Cooldown set after notification");
  const cooldownUntil = storage.get(STORAGE_KEYS.GMAIL_NOTIFY_COOLDOWN_UNTIL);
  const cooldownMs = cooldownUntil - Date.now();
  console.log(`  cooldown_until=${new Date(cooldownUntil).toISOString()}`);
  if (cooldownMs > 0 && cooldownMs <= 5 * 60 * 1000) {
    console.log("  ✅ Active (5 min window)");
    passed++;
  } else {
    console.log(`  ❌ Invalid: ${cooldownMs}ms`);
    failed++;
  }

  // Step 6: HIGH email during cooldown → no OS notif, but badge bumps
  console.log("\n[STEP 6] HIGH email during cooldown");
  await chrome.storage.local.set({ [STORAGE_KEYS.GMAIL_NOTIFY_COOLDOWN_UNTIL]: Date.now() + 5 * 60 * 1000 });
  const prevNotif6 = notifLog.length;
  const prevBadge6 = storage.get(STORAGE_KEYS.GMAIL_RISK_COUNT);  // = 2
  await notifyDanger({
    subject: "Fake bank alert",
    from: "attacker@fakesite.com",
    riskScore: 90,
    threatLevel: "critical",
    messageId: "msg006",
    threadId: "thr006",
  });
  const noNewNotif = notifLog.length === prevNotif6;
  const badgeBumpedDuringCooldown = (storage.get(STORAGE_KEYS.GMAIL_RISK_COUNT) || 0) > prevBadge6;
  if (noNewNotif) { console.log("  ✅ No OS notif during cooldown"); passed++; }
  else { console.log("  ❌ Notification fired during cooldown!"); failed++; }
  if (badgeBumpedDuringCooldown) {
    console.log(`  ✅ Badge bumped during cooldown (${prevBadge6} → ${storage.get(STORAGE_KEYS.GMAIL_RISK_COUNT)})`);
    passed++;
  } else {
    console.log("  ❌ Badge NOT bumped during cooldown"); failed++;
  }

  // Summary
  console.log("\n" + "=".repeat(60));
  console.log(`RESULT: ${passed} passed, ${failed} failed`);
  console.log("=".repeat(60));
  if (notifLog.length) {
    console.log("OS Notifications fired:");
    for (const { opts } of notifLog) {
      console.log(`  "${opts.title}"`);
      console.log(`    ${opts.message}`);
      console.log(`    ${opts.contextMessage}`);
    }
  }
  process.exit(failed > 0 ? 1 : 0);
}

main().catch((e) => { console.error("FATAL:", e); process.exit(1); });
