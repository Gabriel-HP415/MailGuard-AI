# MailGuard-AI — Task Breakdown (5 members)

> **Nguyên tắc:** Mỗi task có:
> - ⏱️ **Estimate** (giờ làm)
> - 🎯 **Acceptance criteria** (checklist để biết xong)
> - 📁 **Files touched** (file chính sẽ sửa)
> - 🔗 **Depends on** (cần task khác xong trước)

Làm theo thứ tự **Tier 1 → Tier 2 → Tier 3**. Tier 1 phải xong trước khi Tier 2 bắt đầu, Tier 2 trước Tier 3.

---

## TIERS

| Tier | Mục đích | Thời gian |
|---|---|---|
| Tier 1 | Nền tảng: tất cả mọi người cùng chạy được local | Tuần 1 (5 ngày) |
| Tier 2 | Tính năng chính: AI + Backend + Extension + Web song song | Tuần 2-3 |
| Tier 3 | Polish + Release | Tuần 4 (cuối) |

---

# TIER 1 — NỀN TẢNG (tuần 1) — tất cả 5 người cùng làm

> Mục tiêu: cả nhóm đều `git pull && docker compose up` chạy được full stack.

## T1.0 — Member chính: Setup shared cho cả nhóm — **1 người duy nhất làm** (anh/em leader)

| Field | Value |
|---|---|
| ⏱️ | 3 giờ |
| 🎯 AC | ✅ Repo có branch `develop`. ✅ `docker compose -f docker-compose.dev.yml up` chạy thành công trên 5 máy. ✅ Adminer hiện database lên được. |
| 📁 Files | `docker-compose.dev.yml`, `backend/Dockerfile.dev`, `backend/requirements-dev.txt`, `deployment/postgres/init.sql`, `CONTRIBUTING.md` |
| 🔗 Deps | — |
| 👉 Ghi chú | Sau khi xong, báo cả nhóm `git pull -r` |

**Steps:**
1. Push nhánh `develop` lên GitHub:
   ```bash
   git checkout -b develop && git push origin develop
   git branch --set-upstream-to=origin/develop develop
   ```
2. Tạo GitHub branch protection: yêu cầu PR + 1 reviewer trước khi merge
3. Verify: 5 người chạy `docker compose -f docker-compose.dev.yml up -d` đều có `/health` trả 200.

## T1.1 — M1 (Backend): Viết `pytest.ini` + `conftest.py` để test chạy được

| Field | Value |
|---|---|
| ⏱️ | 4 giờ |
| 🎯 AC | ✅ `pytest -q` chạy từ `/backend` pass hết. ✅ Test cũ vẫn pass. ✅ Thêm test cho `/predictions`, `/lists`, `/admin`. |
| 📁 Files | `backend/pytest.ini`, `backend/tests/conftest.py`, `backend/tests/test_auth.py`, `backend/tests/test_predictions.py` (new), `backend/tests/test_lists.py` (new), `backend/tests/test_admin.py` (new) |
| 🔗 Deps | T1.0 |
| 👉 Ghi chú | Dùng factory_boy tạo user mẫu. Aim ≥ 60% coverage cho `app/api/v1/` |

**Test mẫu cho predictions:**
```python
def test_predictions_requires_auth(client):
    resp = client.post("/api/v1/predictions", json={
        "email": {"subject": "...", "sender": "...", "body_text": "..."}
    })
    assert resp.status_code == 401
```

## T1.2 — M5 (DevOps): Bật GitHub Actions CI, thêm badge vào README

| Field | Value |
|---|---|
| ⏱️ | 3 giờ |
| 🎯 AC | ✅ Badge ![CI](https://img.shields.io/...) hiển thị xanh trên README. ✅ PR mở ra → CI auto-run → fail nếu vi phạm lint. |
| 📁 Files | `.github/workflows/backend-ci.yml` (có sẵn), thêm `.github/workflows/frontend-ci.yml` (new), `.github/workflows/extension-ci.yml` (new), update `README.md` |
| 🔗 Deps | T1.1 |

## T1.3 — M4 (Frontend): Setup frontend skeleton (npm + Vite)

| Field | Value |
|---|---|
| ⏱️ | 6 giờ |
| 🎯 AC | ✅ `cd frontend && npm install && npm run dev` chạy được. ✅ Login page gọi được `POST /api/v1/auth/login` tới backend dev. ✅ CORS setup đúng (hiện đang là HTML tĩnh). |
| 📁 Files | `frontend/package.json` (new), `frontend/vite.config.js` (new), `frontend/src/main.js`, refactor các `*.html` thành components |
| 🔗 Deps | T1.0 |

## T1.4 — M3 (Extension): Smoke test trên máy mỗi người

| Field | Value |
|---|---|
| ⏱️ | 2 giờ |
| 🎯 AC | ✅ Mỗi người load unpacked được trên Chrome của mình. ✅ Popup mở → gọi được `/health` backend dev. ✅ "Connect Gmail" chạy (sẽ hiện lỗi nếu chưa có Gmail test user). |
| 📁 Files | — |
| 🔗 Deps | T1.0 |

## T1.5 — M2 (AI): Setup model training pipeline skeleton

| Field | Value |
|---|---|
| ⏱️ | 4 giờ |
| 🎯 AC | ✅ Một `python -m ai_service.scripts.train_baseline` chạy được trên dataset mẫu. ✅ Output model ở `ai_service/models/artifacts/baseline_v1.joblib`. ✅ Inference endpoint `/predict` trả JSON. |
| 📁 Files | `ai_service/scripts/train_baseline.py` (new), `ai_service/scripts/dataset_loader.py` (new), `ai_service/inference/app.py` (refactor), `ai_service/Dockerfile.dev` (new) |
| 🔗 Deps | T1.0 |

---

# TIER 2 — TÍNH NĂNG CHÍNH (tuần 2-3) — chia 5 người song song

## M1 — BACKEND API (Member 1)

### T2.M1.1 — Rate limiting middleware (giảm abuse)
- ⏱️ 3h — AC: POST > 60/min → 429. — `app/middleware/`, `tests/test_rate_limit.py`

### T2.M1.2 — Pagination + filter cho `/predictions`
- ⏱️ 4h — AC: `?limit=20&offset=0&predicted_class=phishing` hoạt động. — `app/api/v1/predictions.py`

### T2.M1.3 — Whitelist/Blacklist API test suite
- ⏱️ 4h — AC: ≥ 8 test cases pass. — `tests/test_lists.py`

### T2.M1.4 — `/auth/gmail/login` test (cho OAuth flow mới)
- ⏱️ 5h — AC: mock Google tokeninfo → assert trả JWT + tạo user. — `tests/test_auth_gmail.py`

### T2.M1.5 — Email submit endpoint (nhận raw email → predict → lưu DB)
- ⏱️ 5h — AC: POST 1 email mẫu → trả prediction_id. — `app/api/v1/emails.py`

---

## M2 — AI/ML MODEL (Member 2)

### T2.M2.1 — Baseline TF-IDF + Logistic Regression
- ⏱️ 6h — AC: F1 ≥ 0.85 trên tập test Enron. Lưu model → `models/artifacts/baseline_v1.joblib`. — `ai_service/scripts/train_baseline.py`

### T2.M2.2 — DistilBERT fine-tune (chỉ khi M2.1 xong sớm)
- ⏱️ 12h — AC: F1 ≥ 0.92. — `ai_service/scripts/train_distilbert.py`

### T2.M2.3 — Phishing URL extractor (regex + tld analysis)
- ⏱️ 5h — AC: extract được list URLs từ body + score suspicious. — `ai_service/feature_extraction/url_extractor.py`

### T2.M2.4 — Model versioning + A/B test framework
- ⏱️ 6h — AC: 2 version, request traffic chia % theo weight. — `ai_service/inference/router.py`

### T2.M2.5 — Explainability (SHAP / LIME) integration
- ⏱️ 5h — AC: trả về top-10 features cho mỗi prediction. — `ai_service/explainability/`

---

## M3 — CHROME EXTENSION (Member 3)

### T2.M3.1 — Content script: highlight email nghi ngờ trong Gmail UI
- ⏱️ 6h — AC: Mở Gmail thấy banner đỏ/cam trên email phishing. — `chrome_extension/content/highlighter.js`

### T2.M3.2 — Popup dashboard: hiện stats (high-risk count, last scan)
- ⏱️ 5h — AC: đăng nhập Gmail xong → popup có 3 stat tile hoạt động. — `chrome_extension/popup/popup.html`, `popup.js`, `popup.css`

### T2.M3.3 — Options page: scan cadence + enable/disable labelling
- ⏱️ 4h — AC: Thay đổi setting → áp dụng trong vòng 30s. — `chrome_extension/options/`

### T2.M3.4 — i18n: tiếng Việt cho popup + options
- ⏱️ 3h — AC: Bật Chrome language Vietnamese → UI đổi hết. — `chrome_extension/_locales/vi/messages.json`

### T2.M3.5 — Extension icon thay đổi theo threat level (badge)
- ⏱️ 4h — AC: Mở Gmail thấy icon extension có badge số đỏ. — `chrome_extension/background/service-worker.js`

---

## M4 — FRONTEND WEB (Member 4)

### T2.M4.1 — Login/Register pages với form validation
- ⏱️ 5h — AC: Đăng nhập + đăng ký chạy với backend dev. — `frontend/src/pages/Login.js`, `Register.js`

### T2.M4.2 — Dashboard: list predictions + filter
- ⏱️ 6h — AC: Load 20 prediction mới nhất + filter theo class. — `frontend/src/pages/Dashboard.js`

### T2.M4.3 — Whitelist/Blacklist management UI
- ⏱️ 5h — AC: Thêm/xoá entry, persist xuống backend. — `frontend/src/pages/Lists.js`

### T2.M4.4 — Dark mode + responsive (mobile-friendly)
- ⏱️ 4h — AC: Dark mode toggle lưu vào localStorage. — `frontend/src/styles/`

### T2.M4.5 — Admin page: user management
- ⏱️ 6h — AC: Admin login thấy user list, ban/unban hoạt động. — `frontend/src/pages/Admin.js`

---

## M5 — DEVOPS / DOCS (Member 5)

### T2.M5.1 — GitHub Actions: thêm frontend CI + extension CI
- ⏱️ 4h — AC: Frontend PR → CI chạy ESLint + Jest. Extension PR → CI validate manifest.json. — `.github/workflows/`

### T2.M5.2 — OpenAPI/Swagger auto-deploy lên GitHub Pages
- ⏱️ 4h — AC: https://gabriel-hp415.github.io/MailGuard-AI/ hiện API docs. — `.github/workflows/api-docs.yml`

### T2.M5.3 — Docker Compose cho người dùng cuối (1-click install)
- ⏱️ 3h — AC: `docker compose up` từ clone → truy cập `localhost:8080` thấy UI. — `Dockerfile.docker-compose` ở root.

### T2.M5.4 — User guide + video demo cho đồ án
- ⏱️ 5h — AC: `docs/USER_GUIDE.md` có ảnh step-by-step + link YouTube. — `docs/USER_GUIDE.md`

### T2.M5.5 — Issue templates + PR template
- ⏱️ 2h — AC: Tạo issue "Bug report" → có form sẵn. PR template có checklist. — `.github/ISSUE_TEMPLATE/`, `.github/PULL_REQUEST_TEMPLATE.md`

---

# TIER 3 — POLISH + RELEASE (tuần 4) — tất cả cùng làm

## T3.0 — Code freeze (Thứ 2 tuần 4)
Không merge feature mới. Chỉ fix bug.

## T3.1 — M1: Fix tất cả bug báo từ T3.0 người dùng thật test
- ⏱️ 8h — AC: 0 bug open. — `backend/app/`

## T3.2 — M2: Đo metric (precision/recall/F1) trên golden testset
- ⏱️ 4h — AC: Bảng metric đầy đủ trong `docs/MODEL_METRICS.md`.

## T3.3 — M3: Submit Chrome Web Store (optional)
- ⏱️ 6h — AC: Submit form complete, status "In review". — `chrome-web-store/` (screenshots, copy, privacy)

## T3.4 — M4: Polishing UI, fix responsive + A11y (a11y = accessibility cho người khuyết tật)
- ⏱️ 6h — AC: Lighthouse score ≥ 90 trên login + dashboard.

## T3.5 — M5: Viết báo cáo capstone + slide thuyết trình
- ⏱️ 10h — AC: `docs/CAPSTONE_REPORT.pdf` (15-20 trang), slide PDF 10 trang.

---

# PHỤ LỤC — URGENT FIXES (nên làm đầu tiên)

## U.1 — Backend: rate-limit missing
- File: `backend/app/middleware/`
- Hiện có file folder nhưng cần verify hoạt động. Nếu chưa, thêm middleware theo pattern hiện có.

## U.2 — Extension: bugs nhỏ còn lại sau khi em fix lỗi service worker
- Test 3 user flows: (1) Email/password login fallback (2) Connect Gmail OAuth (3) Scan inbox + highlight email
- Nếu bất kỳ flow nào fail → log issue + fix

## U.3 — AI: chưa có model thật
- File: `ai_service/models/artifacts/` (rỗng)
- Hiện backend gọi sang `AI_PROVIDER` env: nếu `gemini` thì cần key, nếu `stub` thì trả random. Cần train baseline model TF-IDF + save artifact.

---

# CHECKLIST TỔNG CHO NHÓM TRƯỞNG

- [ ] Tier 1 tất cả tasks xong trước 5 ngày
- [ ] Mỗi cuối tuần có PR `develop → main` để demo GV
- [ ] Mỗi member commit ít nhất 1 PR/tuần
- [ ] Không có file > 300 dòng chưa qua review
- [ ] README cập nhật theo mỗi release
- [ ] Test coverage backend ≥ 60%
