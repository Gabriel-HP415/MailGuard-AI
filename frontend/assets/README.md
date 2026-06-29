# Frontend assets (populated by `scripts/fetch_frontend_assets.py`)

This folder is intentionally checked in only as placeholders. Before serving
the dashboard, populate the files by running:

```bash
python scripts/fetch_frontend_assets.py
```

This downloads:
- `css/bootstrap.min.css`  (Bootstrap 5.3.3 CSS)
- `vendor/bootstrap.bundle.min.js`  (Bootstrap JS, popper.js included)
- `vendor/chart.umd.min.js`  (Chart.js 4.4.4 for analytics)

The script is idempotent — running it twice is harmless. If you want to
vendor a different version of Bootstrap, edit `scripts/fetch_frontend_assets.py`.