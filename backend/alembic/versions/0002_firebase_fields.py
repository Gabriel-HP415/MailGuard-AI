"""add Firebase auth fields to users

Revision ID: 0002_firebase_fields
Revises: 0001_initial
Create Date: 2026-06-29 23:00:00.000000

Adds:
- users.firebase_uid VARCHAR(128) NULL UNIQUE  (Firebase identity UID)
- users.auth_provider VARCHAR(20) NOT NULL DEFAULT 'local'
- ix_users_firebase_uid index
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_firebase_fields"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add Firebase columns to the users table."""
    op.add_column(
        "users",
        sa.Column(
            "firebase_uid",
            sa.String(128),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "auth_provider",
            sa.String(20),
            nullable=False,
            server_default="local",
        ),
    )
    op.create_index("ix_users_firebase_uid", "users", ["firebase_uid"], unique=True)


def downgrade() -> None:
    """Reverse the Firebase fields addition."""
    op.drop_index("ix_users_firebase_uid", table_name="users")
    op.drop_column("users", "auth_provider")
    op.drop_column("users", "firebase_uid")