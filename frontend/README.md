# MailGuard-AI — Dashboard (Frontend)

The dashboard is a static single-page site that talks to the backend API.

## Tech

- Plain HTML + ES2017 JavaScript (no framework)
- Bootstrap 5.3 (vendored locally)
- Chart.js 4.4 (vendored locally)
- All API calls are authenticated with a JWT stored in `localStorage`

## Folder layout

```
frontend/
├── index.html              # Redirects to login or dashboard
├── login.html              # Sign in
├── register.html           # Sign up
├── dashboard.html          # User dashboard (stats + charts + recent predictions)
├── predictions.html        # Full list of predictions with filters
├── prediction.html         # Single prediction detail + feedback
├── lists.html              # Whitelist & Blacklist management
├── admin.html              # Admin only — model version management
├── partials/
│   └── navbar.html         # <template> used by UI.mountNavbar()
├── assets/
│   ├── css/
│   │   ├── bootstrap.min.css      # populated by fetch_frontend_assets.py
│   │   └── app.css                # our overrides on top of Bootstrap
│   ├── vendor/
│   │   ├── bootstrap.bundle.min.js
│   │   └── chart.umd.min.js
│   └── js/
│       ├── api.js                 # MailGuardAPI class
│       ├── ui.js                  # navbar, auth guard, toasts, formatting
│       ├── auth.js                # login page logic
│       ├── dashboard.js           # dashboard page logic
│       ├── predictions.js         # predictions list logic
│       ├── prediction-detail.js   # single prediction + feedback
│       ├── lists.js               # whitelist/blacklist CRUD
│       └── admin.js               # admin model management
├── Dockerfile              # nginx:alpine, multi-stage with asset fetch
└── Dockerfile.nginx        # nginx server config
```

## Run locally (no Docker)

1. Pull the vendored assets (one-time):
   ```bash
   python scripts/fetch_frontend_assets.py
   ```
2. Serve the directory with any static server:
   ```bash
   # Python
   python -m http.server 8080 --directory frontend

   # or Node
   npx serve frontend -l 8080
   ```
3. Open <http://localhost:8080/> — it redirects you to the login page.
4. The default backend URL points to `http://localhost:8000/api/v1`.
   Change it from the login page (Backend settings link).

## Auth model

- After login, the access token is stored in `localStorage.mg_token`.
- The user profile is cached in `localStorage.mg_user`.
- Token is automatically sent as `Authorization: Bearer <token>` on every API call.
- On `401`, the client clears the token and redirects to `/login.html`.

## Page-level auth

Set `<meta name="page-auth" content="required">` (or `admin`) to automatically
redirect unauthenticated users to the login screen. The navbar reads
`api.user.role` to decide whether to show the admin link.

## Run with Docker

```bash
docker build -t mailguard-frontend -f frontend/Dockerfile .
docker run --rm -p 8080:80 mailguard-frontend
```

## Customizing the backend URL

In each HTML page, before `assets/js/api.js`:
```html
<script>window.MAILGUARD_API_BASE_URL = "https://api.mailguard.ai/api/v1";</script>
```

Per-user overrides are saved in `localStorage.mg_baseUrl` and persist across
browser sessions.