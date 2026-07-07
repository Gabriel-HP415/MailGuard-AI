/**
 * Quick smoke test for the updated stub classifier.
 * Tests the three PayPal phishing emails the user reported.
 */
const fs = require("fs");

async function httpPost(url, body, headers = {}) {
  const { hostname, port, pathname, search } = new URL(url);
  return new Promise((resolve, reject) => {
    const opts = {
      hostname, port: port || 80,
      path: pathname + search, method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
    };
    const req = require("http").request(opts, (res) => {
      let data = "";
      res.on("data", c => data += c);
      res.on("end", () => resolve({ status: res.statusCode, data: JSON.parse(data) }));
    });
    req.on("error", reject);
    req.write(JSON.stringify(body));
    req.end();
  });
}

async function main() {
  const login = await httpPost(
    "http://127.0.0.1:8003/api/v1/auth/login",
    { email: "admin@mailguard.ai", password: "ChangeMe123!" }
  );
  const token = login.data.access_token;
  console.log("Login OK");

  const tests = [
    { file: "scripts/_test_paypal1.json",   expect: "scam" },
    { file: "scripts/_test_paypal2.json",   expect: "normal" },
    { file: "scripts/_test_apple.json",      expect: "scam" },
  ];

  for (const { file, expect } of tests) {
    const body = JSON.parse(fs.readFileSync(file, "utf-8"));
    const resp = await httpPost(
      "http://127.0.0.1:8003/api/v1/predictions", body,
      { Authorization: `Bearer ${token}` }
    );
    const d = resp.data;
    const pred = d.predicted_class;
    const risk = d.risk_score;
    const threat = d.threat_level;
    const urls = (d.suspicious_urls || []).map(u => `${u.url} (${u.reason || "score:"+u.score})`).join(", ") || "none";
    const signals = d.explanation?.matched_signals?.slice(0, 6).join(", ") || "none";
    const ok = pred.toLowerCase() === expect.toLowerCase() ? "✅" : "❌";
    console.log(`\n${ok} ${file}`);
    console.log(`   class=${pred} risk=${risk} threat=${threat}`);
    console.log(`   URLs: ${urls}`);
    console.log(`   signals: ${signals}`);
    console.log(`   (expected: ${expect})`);
  }
}

main().catch(console.error);
