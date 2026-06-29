# MailGuard-AI — Entity-Relationship diagram

This document describes the conceptual schema. The physical schema lives
in `backend/alembic/versions/0001_initial.py` (SQLAlchemy + MySQL).

## Diagram (Mermaid)

```mermaid
erDiagram
    USERS {
        int id PK
        string email
        string username
        string password_hash
        string full_name
        enum role
        bool is_active
        bool is_verified
        datetime last_login_at
        datetime created_at
        datetime updated_at
    }

    EMAILS {
        int id PK
        int user_id FK
        string gmail_id
        string sender
        string sender_domain
        string recipient
        string subject
        text body_text
        text body_html
        json links
        json attachments
        bool has_attachments
        datetime received_at
        datetime created_at
    }

    PREDICTIONS {
        int id PK
        int email_id FK
        int user_id FK
        int model_version_id FK
        enum predicted_class
        int class_index
        float confidence
        float risk_score
        enum threat_level
        json probabilities
        json explanation
        json highlighted_spans
        json suspicious_urls
        int inference_time_ms
        datetime created_at
    }

    FEEDBACK {
        int id PK
        int prediction_id FK
        int user_id FK
        bool is_correct
        enum correct_class
        text comment
        datetime created_at
    }

    WHITELIST {
        int id PK
        int user_id FK
        string sender
        string domain
        text note
        datetime created_at
    }

    BLACKLIST {
        int id PK
        int user_id FK
        string sender
        string domain
        text reason
        datetime created_at
    }

    MODEL_VERSIONS {
        int id PK
        string version
        string algorithm
        float accuracy
        string artifact_path
        text description
        bool is_active
        datetime created_at
    }

    ACTIVITY_LOGS {
        int id PK
        int user_id FK
        string action
        string entity_type
        int entity_id
        string ip_address
        text user_agent
        string status
        json details
        datetime created_at
    }

    USERS ||--o{ EMAILS : "owns"
    USERS ||--o{ PREDICTIONS : "requested"
    USERS ||--o{ FEEDBACK : "submitted"
    USERS ||--o{ WHITELIST : "added"
    USERS ||--o{ BLACKLIST : "added"
    USERS ||--o{ ACTIVITY_LOGS : "performed"

    EMAILS ||--o{ PREDICTIONS : "classified_as"
    PREDICTIONS ||--o{ FEEDBACK : "received"
    MODEL_VERSIONS ||--o{ PREDICTIONS : "produced"
```

## Class taxonomy (`predicted_class`)

| Index | Label | Meaning |
|-------|-------|---------|
| 0 | `normal` | Legitimate personal/work correspondence. |
| 1 | `notification` | Transactional / system messages (orders, alerts, reminders). |
| 2 | `spam` | Unsolicited marketing / bulk mail. |
| 3 | `scam` | Phishing, fraud, account takeover, malware. |

## Threat level (`threat_level`)

| Level | Risk score | Action |
|-------|-----------|--------|
| `low` | 0–24 | Informational banner. |
| `medium` | 25–49 | Warning banner. |
| `high` | 50–74 | Strong warning + suggested review. |
| `critical` | 75–100 | Hard block recommended. |

## Indexes (recommended)

- `users(email) UNIQUE`, `users(username) UNIQUE`
- `emails(user_id, created_at DESC)`
- `predictions(user_id, created_at DESC)`,
  `predictions(predicted_class)`, `predictions(email_id)`
- `feedback(user_id, created_at DESC)`
- `model_versions(is_active)` partial index (only one row is TRUE)
- `activity_logs(user_id, created_at DESC)`,
  `activity_logs(action, entity_type, entity_id)`

## Sample row counts (reference, varies by usage)

| Table | Typical size |
|-------|-------------|
| `users`         | 1–100s      |
| `emails`        | 100–100K per user |
| `predictions`   | 1:1 with `emails` |
| `feedback`      | ~10% of predictions |
| `whitelist/blacklist` | <100 per user |
| `model_versions`| <50 (audit only) |
| `activity_logs` | grows with traffic; consider 90-day retention |