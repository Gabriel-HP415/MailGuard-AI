# MailGuard-AI — Sequence diagrams

## 1. End-to-end classification (UC-01)

```mermaid
sequenceDiagram
    participant U as User (Gmail)
    participant E as Chrome Extension
    participant B as Backend API
    participant DB as MySQL
    participant AI as AI Service

    U->>E: opens email
    E->>E: scrape Gmail DOM
    E->>B: POST /api/v1/predictions (JWT)
    B->>DB: INSERT Email
    B->>AI: POST /predict
    AI->>AI: clean → classify → risk → XAI
    AI-->>B: prediction JSON
    B->>DB: INSERT Prediction
    B->>DB: INSERT ActivityLog
    B-->>E: 201 + Prediction
    E->>E: render banner + highlights
```

## 2. Feedback submission (UC-02)

```mermaid
sequenceDiagram
    participant U as User
    participant E as Chrome Extension
    participant B as Backend API
    participant DB as MySQL

    U->>E: clicks "✅ Mark correct"
    E->>B: POST /api/v1/feedback
    B->>DB: verify prediction belongs to user
    B->>DB: INSERT Feedback
    B->>DB: INSERT ActivityLog
    B-->>E: 201 + Feedback
    E-->>U: toast "Thanks!"
```

## 3. Login (UC-04-prep)

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend (login.html)
    participant B as Backend API
    participant DB as MySQL

    U->>FE: submit email + password
    FE->>B: POST /api/v1/auth/login
    B->>DB: SELECT user WHERE email
    B->>B: verify bcrypt
    B->>DB: UPDATE last_login_at
    B-->>FE: 200 + JWT
    FE->>FE: store JWT + user in localStorage
    FE-->>U: redirect to /dashboard.html
```

## 4. Publish model + activate (UC-05)

```mermaid
sequenceDiagram
    participant ML as ML engineer
    participant AI as AI Service
    participant FS as File system
    participant B as Backend API
    participant DB as MySQL

    ML->>AI: python -m ai_service.scripts.train_baseline naive_bayes --augment --evaluate --publish --activate
    AI->>FS: save joblib artifact
    AI->>AI: evaluate on hold-out → report.json + report.md
    AI->>B: POST /api/v1/auth/login (admin)
    B-->>AI: JWT
    AI->>B: POST /api/v1/admin/models (+ JWT)
    B->>DB: INSERT ModelVersion (is_active=false)
    B-->>AI: 201 + id
    AI->>B: POST /api/v1/admin/models/{id}/activate
    B->>DB: UPDATE all SET is_active=false
    B->>DB: UPDATE id SET is_active=true
    B-->>AI: 200 + activated MV
```

## 5. A/B testing request (UC-07)

```mermaid
sequenceDiagram
    participant C as Client
    participant S as AI Service
    participant A as Model A (active)
    participant B as Model B (challenger)

    C->>S: POST /predict (body)
    S->>S: assign bucket (default 80/20)
    alt bucket = A
        S->>A: predict → JSON
        A-->>S: {ab_bucket:"A", ...}
    else bucket = B
        S->>B: predict → JSON
        B-->>S: {ab_bucket:"B", ...}
    end
    S-->>C: 200 + result
```

## 6. Whitelist match (future enhancement)

```mermaid
sequenceDiagram
    participant E as Extension
    participant B as Backend API
    participant DB as MySQL

    E->>B: POST /api/v1/predictions
    B->>DB: SELECT whitelist WHERE user AND sender
    alt match
        B-->>E: short-circuit {predicted_class:"normal", ab_bucket:"WL"}
    else no match
        B->>B: forward to AI Service
    end
```