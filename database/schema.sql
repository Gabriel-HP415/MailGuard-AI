-- ============================================
-- MailGuard-AI — MySQL 8 Schema (DDL)
-- ============================================
-- Database: mailguard_ai
-- Charset: utf8mb4 / utf8mb4_unicode_ci
-- ============================================

CREATE DATABASE IF NOT EXISTS `mailguard_ai`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE `mailguard_ai`;

-- --------------------------------------------
-- 1. users — Người dùng hệ thống
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
    `id`            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `email`         VARCHAR(255)    NOT NULL,
    `username`      VARCHAR(100)    NOT NULL,
    `password_hash` VARCHAR(255)    NOT NULL,
    `full_name`     VARCHAR(150)    NULL,
    `role`          ENUM('user','admin') NOT NULL DEFAULT 'user',
    `is_active`     TINYINT(1)      NOT NULL DEFAULT 1,
    `is_verified`   TINYINT(1)      NOT NULL DEFAULT 0,
    `avatar_url`    VARCHAR(500)    NULL,
    `last_login_at` DATETIME        NULL,
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_users_email` (`email`),
    UNIQUE KEY `uq_users_username` (`username`),
    KEY `ix_users_role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------
-- 2. emails — Lưu nội dung email đã phân tích
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS `emails` (
    `id`             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id`        BIGINT UNSIGNED NOT NULL,
    `gmail_id`       VARCHAR(255)    NULL,
    `sender`         VARCHAR(255)    NOT NULL,
    `sender_domain`  VARCHAR(255)    NULL,
    `recipient`      VARCHAR(255)    NULL,
    `subject`        VARCHAR(1000)   NULL,
    `body_text`      MEDIUMTEXT      NULL,
    `body_html`      MEDIUMTEXT      NULL,
    `links_json`     JSON            NULL,
    `attachments_json` JSON          NULL,
    `has_attachments` TINYINT(1)     NOT NULL DEFAULT 0,
    `received_at`    DATETIME        NULL,
    `created_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `ix_emails_user_id` (`user_id`),
    KEY `ix_emails_sender` (`sender`),
    KEY `ix_emails_sender_domain` (`sender_domain`),
    KEY `ix_emails_gmail_id` (`gmail_id`),
    CONSTRAINT `fk_emails_user`
        FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------
-- 3. predictions — Kết quả dự đoán của AI
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS `predictions` (
    `id`              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `email_id`        BIGINT UNSIGNED NOT NULL,
    `user_id`         BIGINT UNSIGNED NOT NULL,
    `model_version_id` BIGINT UNSIGNED NOT NULL,
    `predicted_class` ENUM('normal','notification','spam','scam') NOT NULL,
    `class_index`     TINYINT UNSIGNED NOT NULL,
    `confidence`      DECIMAL(5,4)     NOT NULL,
    `risk_score`      DECIMAL(5,2)     NOT NULL,
    `threat_level`    ENUM('low','medium','high','critical') NOT NULL DEFAULT 'low',
    `probabilities_json` JSON          NULL,
    `explanation_json`   JSON          NULL,
    `highlighted_spans_json` JSON      NULL,
    `suspicious_urls_json` JSON        NULL,
    `inference_time_ms` INT UNSIGNED   NULL,
    `created_at`      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `ix_predictions_email_id` (`email_id`),
    KEY `ix_predictions_user_id` (`user_id`),
    KEY `ix_predictions_model_version_id` (`model_version_id`),
    KEY `ix_predictions_predicted_class` (`predicted_class`),
    KEY `ix_predictions_created_at` (`created_at`),
    CONSTRAINT `fk_predictions_email`
        FOREIGN KEY (`email_id`) REFERENCES `emails`(`id`)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_predictions_user`
        FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_predictions_model_version`
        FOREIGN KEY (`model_version_id`) REFERENCES `model_versions`(`id`)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------
-- 4. feedback — Phản hồi của người dùng
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS `feedback` (
    `id`              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `prediction_id`   BIGINT UNSIGNED NOT NULL,
    `user_id`         BIGINT UNSIGNED NOT NULL,
    `is_correct`      TINYINT(1)      NOT NULL,
    `correct_class`   ENUM('normal','notification','spam','scam') NULL,
    `comment`         TEXT            NULL,
    `created_at`      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `ix_feedback_prediction_id` (`prediction_id`),
    KEY `ix_feedback_user_id` (`user_id`),
    KEY `ix_feedback_is_correct` (`is_correct`),
    CONSTRAINT `fk_feedback_prediction`
        FOREIGN KEY (`prediction_id`) REFERENCES `predictions`(`id`)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_feedback_user`
        FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------
-- 5. whitelist — Danh sách người gửi tin cậy
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS `whitelist` (
    `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id`    BIGINT UNSIGNED NOT NULL,
    `sender`     VARCHAR(255)    NOT NULL,
    `domain`     VARCHAR(255)    NULL,
    `note`       VARCHAR(500)    NULL,
    `created_at` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_whitelist_user_sender` (`user_id`, `sender`),
    KEY `ix_whitelist_domain` (`domain`),
    CONSTRAINT `fk_whitelist_user`
        FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------
-- 6. blacklist — Danh sách người gửi đáng ngờ
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS `blacklist` (
    `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id`    BIGINT UNSIGNED NOT NULL,
    `sender`     VARCHAR(255)    NOT NULL,
    `domain`     VARCHAR(255)    NULL,
    `reason`     VARCHAR(500)    NULL,
    `created_at` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_blacklist_user_sender` (`user_id`, `sender`),
    KEY `ix_blacklist_domain` (`domain`),
    CONSTRAINT `fk_blacklist_user`
        FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------
-- 7. model_versions — Quản lý phiên bản mô hình
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS `model_versions` (
    `id`           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `version`      VARCHAR(50)     NOT NULL,
    `algorithm`    VARCHAR(100)    NOT NULL,
    `description`  TEXT            NULL,
    `accuracy`     DECIMAL(5,4)    NULL,
    `precision_score` DECIMAL(5,4) NULL,
    `recall`       DECIMAL(5,4)    NULL,
    `f1_score`     DECIMAL(5,4)    NULL,
    `training_samples` INT UNSIGNED NULL,
    `training_duration_sec` INT UNSIGNED NULL,
    `file_path`    VARCHAR(500)    NULL,
    `metrics_json` JSON            NULL,
    `is_active`    TINYINT(1)      NOT NULL DEFAULT 0,
    `created_at`   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_model_versions_version` (`version`),
    KEY `ix_model_versions_is_active` (`is_active`),
    KEY `ix_model_versions_algorithm` (`algorithm`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------
-- 8. activity_logs — Nhật ký hoạt động hệ thống
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS `activity_logs` (
    `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id`    BIGINT UNSIGNED NULL,
    `action`     VARCHAR(100)    NOT NULL,
    `entity_type` VARCHAR(50)    NULL,
    `entity_id`  BIGINT UNSIGNED NULL,
    `ip_address` VARCHAR(45)     NULL,
    `user_agent` VARCHAR(500)    NULL,
    `status`     ENUM('success','failure','warning') NOT NULL DEFAULT 'success',
    `details_json` JSON          NULL,
    `created_at` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `ix_activity_logs_user_id` (`user_id`),
    KEY `ix_activity_logs_action` (`action`),
    KEY `ix_activity_logs_created_at` (`created_at`),
    CONSTRAINT `fk_activity_logs_user`
        FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;