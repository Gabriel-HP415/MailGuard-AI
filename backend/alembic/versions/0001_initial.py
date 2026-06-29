"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-29 21:30:00.000000

Creates all 8 tables for MailGuard-AI (the canonical schema).
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the initial schema."""
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=True),
        sa.Column(
            "role",
            sa.Enum("user", "admin", name="user_role", length=20),
            nullable=False,
            server_default="user",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("last_login_at", sa.DateTime, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # model_versions (must be created before predictions)
    op.create_table(
        "model_versions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("version", sa.String(50), nullable=False, unique=True),
        sa.Column("algorithm", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("accuracy", sa.DECIMAL(5, 4), nullable=True),
        sa.Column("precision_score", sa.DECIMAL(5, 4), nullable=True),
        sa.Column("recall", sa.DECIMAL(5, 4), nullable=True),
        sa.Column("f1_score", sa.DECIMAL(5, 4), nullable=True),
        sa.Column("training_samples", sa.Integer, nullable=True),
        sa.Column("training_duration_sec", sa.Integer, nullable=True),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("metrics", sa.JSON, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_model_versions_is_active", "model_versions", ["is_active"])
    op.create_index("ix_model_versions_algorithm", "model_versions", ["algorithm"])

    # emails
    op.create_table(
        "emails",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, nullable=False),
        sa.Column("gmail_id", sa.String(255), nullable=True),
        sa.Column("sender", sa.String(255), nullable=False),
        sa.Column("sender_domain", sa.String(255), nullable=True),
        sa.Column("recipient", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(1000), nullable=True),
        sa.Column("body_text", sa.Text, nullable=True),
        sa.Column("body_html", sa.Text, nullable=True),
        sa.Column("links", sa.JSON, nullable=True),
        sa.Column("attachments", sa.JSON, nullable=True),
        sa.Column(
            "has_attachments", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column("received_at", sa.DateTime, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", onupdate="CASCADE"
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_emails_user_id", "emails", ["user_id"])
    op.create_index("ix_emails_sender", "emails", ["sender"])
    op.create_index("ix_emails_sender_domain", "emails", ["sender_domain"])
    op.create_index("ix_emails_gmail_id", "emails", ["gmail_id"])

    # predictions
    op.create_table(
        "predictions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("email_id", sa.BigInteger, nullable=False),
        sa.Column("user_id", sa.BigInteger, nullable=False),
        sa.Column("model_version_id", sa.BigInteger, nullable=False),
        sa.Column(
            "predicted_class",
            sa.Enum(
                "normal", "notification", "spam", "scam",
                name="email_class", length=20,
            ),
            nullable=False,
        ),
        sa.Column("class_index", sa.SmallInteger, nullable=False),
        sa.Column("confidence", sa.DECIMAL(5, 4), nullable=False),
        sa.Column("risk_score", sa.DECIMAL(5, 2), nullable=False),
        sa.Column(
            "threat_level",
            sa.Enum(
                "low", "medium", "high", "critical",
                name="threat_level", length=20,
            ),
            nullable=False,
            server_default="low",
        ),
        sa.Column("probabilities", sa.JSON, nullable=True),
        sa.Column("explanation", sa.JSON, nullable=True),
        sa.Column("highlighted_spans", sa.JSON, nullable=True),
        sa.Column("suspicious_urls", sa.JSON, nullable=True),
        sa.Column("inference_time_ms", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(
            ["email_id"], ["emails.id"], ondelete="CASCADE", onupdate="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", onupdate="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["model_versions.id"],
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_predictions_email_id", "predictions", ["email_id"])
    op.create_index("ix_predictions_user_id", "predictions", ["user_id"])
    op.create_index(
        "ix_predictions_model_version_id", "predictions", ["model_version_id"]
    )
    op.create_index(
        "ix_predictions_predicted_class", "predictions", ["predicted_class"]
    )
    op.create_index("ix_predictions_created_at", "predictions", ["created_at"])

    # feedback
    op.create_table(
        "feedback",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("prediction_id", sa.BigInteger, nullable=False),
        sa.Column("user_id", sa.BigInteger, nullable=False),
        sa.Column("is_correct", sa.Boolean, nullable=False),
        sa.Column(
            "correct_class",
            sa.Enum(
                "normal", "notification", "spam", "scam",
                name="correct_class", length=20,
            ),
            nullable=True,
        ),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(
            ["prediction_id"],
            ["predictions.id"],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", onupdate="CASCADE"
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_feedback_prediction_id", "feedback", ["prediction_id"])
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_index("ix_feedback_is_correct", "feedback", ["is_correct"])

    # whitelist
    op.create_table(
        "whitelist",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, nullable=False),
        sa.Column("sender", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", onupdate="CASCADE"
        ),
        sa.UniqueConstraint("user_id", "sender", name="uq_whitelist_user_sender"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_whitelist_domain", "whitelist", ["domain"])

    # blacklist
    op.create_table(
        "blacklist",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, nullable=False),
        sa.Column("sender", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", onupdate="CASCADE"
        ),
        sa.UniqueConstraint("user_id", "sender", name="uq_blacklist_user_sender"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_blacklist_domain", "blacklist", ["domain"])

    # activity_logs
    op.create_table(
        "activity_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.BigInteger, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column(
            "status",
            sa.Enum("success", "failure", "warning", name="activity_status"),
            nullable=False,
            server_default="success",
        ),
        sa.Column("details", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="SET NULL", onupdate="CASCADE"
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_activity_logs_user_id", "activity_logs", ["user_id"])
    op.create_index("ix_activity_logs_action", "activity_logs", ["action"])
    op.create_index("ix_activity_logs_created_at", "activity_logs", ["created_at"])


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("activity_logs")
    op.drop_table("blacklist")
    op.drop_table("whitelist")
    op.drop_table("feedback")
    op.drop_table("predictions")
    op.drop_table("emails")
    op.drop_table("model_versions")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS activity_status")
    op.execute("DROP TYPE IF EXISTS correct_class")
    op.execute("DROP TYPE IF EXISTS email_class")
    op.execute("DROP TYPE IF EXISTS threat_level")
    op.execute("DROP TYPE IF EXISTS user_role")