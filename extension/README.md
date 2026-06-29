# MailGuard-AI Chrome Extension

Manifest V3 Chrome Extension that runs inside Gmail.

## Install (Development)

1. Open `chrome://extensions/`
2. Enable **Developer mode** (top right).
3. Click **Load unpacked** → select this `extension/` folder.

## Folder Layout

```
extension/
├── manifest.json
├── background/      # service worker
├── content/         # Gmail DOM parser + UI injection
├── popup/           # extension popup
├── options/         # settings page
├── assets/          # icons, css, js libs
└── README.md
```

## API Endpoint

The extension posts extracted email data to the backend:

```
POST {BACKEND_URL}/api/v1/predict
Authorization: Bearer <JWT>
```

Configuration is set in the **Options** page or auto-loaded from `.env` defaults.