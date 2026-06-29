# Sơ đồ ER — MailGuard-AI

Sơ đồ thực thể - quan hệ (ER) cho hệ thống MailGuard-AI, gồm 8 bảng chính.

## Sơ đồ ER (Mermaid)

```mermaid
erDiagram
    USERS ||--o{ EMAILS            : "gửi/nhận"
    USERS ||--o{ PREDICTIONS       : "nhận kết quả"
    USERS ||--o{ FEEDBACK          : "đánh giá"
    USERS ||--o{ WHITELIST         : "sở hữu"
    USERS ||--o{ BLACKLIST         : "sở hữu"
    USERS ||--o{ ACTIVITY_LOGS     : "tạo"
    EMAILS ||--|| PREDICTIONS      : "được phân loại"
    PREDICTIONS ||--o{ FEEDBACK    : "có phản hồi"
    MODEL_VERSIONS ||--o{ PREDICTIONS : "sinh ra"

    USERS {
        BIGINT id PK
        VARCHAR email UK
        VARCHAR username UK
        VARCHAR password_hash
        VARCHAR full_name
        ENUM role "user|admin"
        BOOLEAN is_active
        BOOLEAN is_verified
        VARCHAR avatar_url
        DATETIME last_login_at
        DATETIME created_at
        DATETIME updated_at
    }

    EMAILS {
        BIGINT id PK
        BIGINT user_id FK
        VARCHAR gmail_id
        VARCHAR sender
        VARCHAR sender_domain
        VARCHAR recipient
        VARCHAR subject
        TEXT body_text
        TEXT body_html
        JSON links_json
        JSON attachments_json
        BOOLEAN has_attachments
        DATETIME received_at
        DATETIME created_at
    }

    PREDICTIONS {
        BIGINT id PK
        BIGINT email_id FK
        BIGINT user_id FK
        BIGINT model_version_id FK
        ENUM predicted_class "normal|notification|spam|scam"
        TINYINT class_index "0..3"
        DECIMAL confidence "0.0000..1.0000"
        DECIMAL risk_score "0.00..100.00"
        ENUM threat_level "low|medium|high|critical"
        JSON probabilities_json
        JSON explanation_json
        JSON highlighted_spans_json
        JSON suspicious_urls_json
        INT inference_time_ms
        DATETIME created_at
    }

    FEEDBACK {
        BIGINT id PK
        BIGINT prediction_id FK
        BIGINT user_id FK
        BOOLEAN is_correct
        ENUM correct_class
        TEXT comment
        DATETIME created_at
    }

    WHITELIST {
        BIGINT id PK
        BIGINT user_id FK
        VARCHAR sender
        VARCHAR domain
        VARCHAR note
        DATETIME created_at
    }

    BLACKLIST {
        BIGINT id PK
        BIGINT user_id FK
        VARCHAR sender
        VARCHAR domain
        VARCHAR reason
        DATETIME created_at
    }

    MODEL_VERSIONS {
        BIGINT id PK
        VARCHAR version UK
        VARCHAR algorithm
        TEXT description
        DECIMAL accuracy
        DECIMAL precision_score
        DECIMAL recall
        DECIMAL f1_score
        INT training_samples
        INT training_duration_sec
        VARCHAR file_path
        JSON metrics_json
        BOOLEAN is_active
        DATETIME created_at
    }

    ACTIVITY_LOGS {
        BIGINT id PK
        BIGINT user_id FK
        VARCHAR action
        VARCHAR entity_type
        BIGINT entity_id
        VARCHAR ip_address
        VARCHAR user_agent
        ENUM status "success|failure|warning"
        JSON details_json
        DATETIME created_at
    }
```

## Mô tả quan hệ

| Quan hệ | Loại | Mô tả |
|---------|------|-------|
| `users → emails` | 1-N | Một người dùng có nhiều email đã phân tích |
| `emails → predictions` | 1-1 | Mỗi email có đúng một dự đoán |
| `predictions → feedback` | 1-N | Một dự đoán có thể có nhiều phản hồi |
| `users → feedback` | 1-N | Người dùng đánh giá nhiều dự đoán |
| `users → whitelist` | 1-N | Danh sách tin cậy của người dùng |
| `users → blacklist` | 1-N | Danh sách đáng ngờ của người dùng |
| `model_versions → predictions` | 1-N | Một phiên bản mô hình sinh nhiều dự đoán |
| `users → activity_logs` | 1-N | Nhật ký hoạt động của người dùng |

## Chỉ mục (Indexes)

- Khóa chính (PK): tự động.
- Khóa ngoại (FK): tự động lập chỉ mục cho cột khóa ngoại.
- Khóa duy nhất (UQ): `users.email`, `users.username`, `model_versions.version`, `whitelist(user_id, sender)`, `blacklist(user_id, sender)`.
- Chỉ mục phụ: `emails.sender_domain`, `predictions.created_at`, `activity_logs.action`.

## File SQL

Xem file [`schema.sql`](./schema.sql) để lấy DDL đầy đủ.