# MailGuard-AI — Chrome Extension

A Manifest V3 Chrome extension that detects phishing, scam and spam emails
in real-time directly inside Gmail.

## Features

- 🔍 **Real-time scanning** of opened Gmail messages
- 🎨 **Highlight suspicious spans** (keywords + risky URLs) inside the email
  body with tooltips explaining the risk
- 📊 **Banner verdict** with class + risk score + threat level
- 👍👎 **One-click feedback** for Human-in-the-loop improvement
- 🛡️ **Whitelist / Blacklist** management from the options page
- 🔐 **JWT auth** with token stored in `chrome.storage.local`
- ⚙️ **Configurable backend URL** (works against any MailGuard-AI deployment)

## Folder layout

```
chrome_extension/
├── manifest.json
├── icons/
│   └── README.md              # Icon placeholder notes
├── lib/
│   ├── api.js                 # MailGuardAPI singleton
│   └── ui.js                  # Toasts / helpers
├── background/
│   └── service-worker.js      # Auth + message broker
├── content/
│   ├── gmail-scraper.js       # DOM extraction
│   ├── highlighter.js         # Apply prediction UI
│   ├── bootstrap.js           # Wire everything up
│   └── styles.css
├── popup/
│   ├── popup.html
│   ├── popup.css
│   └── popup.js
└── options/
    ├── options.html
    ├── options.css
    └── options.js
```

## Install (development)

1. Open `chrome://extensions/`.
2. Enable **Developer mode** (top-right).
3. Click **Load unpacked** and select this `chrome_extension/` folder.
4. Pin **MailGuard-AI** to the toolbar.
5. Open the extension popup, click **Manage lists & settings**, then sign in.
6. Open Gmail — MailGuard-AI will start analyzing each email automatically.

## Build for production

```bash
# From the project root
python scripts/build_extension.py
```

This packages the source into `dist/mailguard-ai-extension-vX.Y.Z.zip`
ready for the Chrome Web Store.

## Permissions

| Permission | Why |
|------------|-----|
| `storage` | Persist JWT + user settings |
| `activeTab` | Read current Gmail tab |
| `scripting` | Inject content scripts when needed |
| `tabs` | Listen for tab events |

## Hosting

The extension talks to the backend at the URL configured in the Options page
(default `http://localhost:8000/api/v1`). For production, point it at your
deployed backend (e.g. `https://api.mailguard.ai/api/v1`).

## Testing

Manual:
1. Open Gmail.
2. Click on a marketing / spam email.
3. Verify the banner appears with the correct verdict + highlighted spans.

Automated:
- The content scripts are intentionally framework-free. For unit tests, use
  `jest` with `jsdom` and import the relevant modules (e.g. `lib/api.js`).