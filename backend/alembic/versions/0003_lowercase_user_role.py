"""Fix enum casing to match Python enum `values`.

The original 0001_initial migration created Postgres enums with mixed casing:
    user_role:        "USER", "ADMIN"        (uppercase)
    email_class:      "normal", "notification", "spam", "scam"   (lowercase)
    threat_level:     "low", "medium", "high", "critical"          (lowercase)

But the SQLAlchemy models now pass `values_callable=lambda e: [e.value for e in e]`
so they INSERT the lowercase values produced by Python's str-Enum. That meant:
    user_role could insert "admin" (failed against DB uppercase enum)
    email_class could insert "NORMAL" (failed against DB lowercase enum)

This migration aligns both Postgres enums to the Python enum values:

    email_class  -> 'normal', 'notification', 'spam', 'scam'   (unchanged)
    threat_level -> 'low', 'medium', 'high', 'critical'         (unchanged)
    user_role    -> 'user', 'admin'                             (NEW: lowercase)

For email_class / threat_level we keep existing rows but the enum already
happens to agree with Python, so no data conversion is needed.

For user_role the casing flips, so we have to:
    1. Rename existing column to a temporary text column
    2. Drop & recreate the enum type in lowercase
    3. Re-add the column using the new enum, lowercasing the data
    4. Drop the temp column

Revision ID: 0003_lowercase_user_role
Revises: 0002_firebase_fields
Create Date: 2026-07-05 21:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_lowercase_user_role"
down_revision = "0002_firebase_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- Step 0: drop DEFAULT first so we can drop the type later ----
    op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")

    # ---- Step 1: rename users.role -> role_tmp (text) ----
    op.alter_column("users", "role", new_column_name="role_tmp",
                    existing_type=sa.String(20), existing_nullable=False,
                    type_=sa.String(20))
    op.execute("DROP TYPE IF EXISTS user_role CASCADE")

    # ---- Step 2: recreate user_role enum with lowercase values ----
    user_role = sa.Enum("user", "admin", name="user_role", length=20)
    user_role.create(op.get_bind(), checkfirst=True)

    # ---- Step 3: re-add users.role with the new enum + backfill ----
    op.add_column(
        "users",
        sa.Column("role", user_role, nullable=False, server_default="user"),
    )
    op.execute(
        "UPDATE users SET role = LOWER(role_tmp)::user_role "
        "WHERE role_tmp IS NOT NULL"
    )

    # ---- Step 4: drop temp ----
    op.drop_column("users", "role_tmp")
    op.create_index("ix_users_role", "users", ["role"])


def downgrade() -> None:
    # Reverse: convert back to uppercase
    op.alter_column("users", "role", new_column_name="role_tmp",
                    type_=sa.String(20), existing_nullable=False)
    op.execute("DROP TYPE IF EXISTS user_role")
    user_role_up = sa.Enum("USER", "ADMIN", name="user_role", length=20)
    user_role_up.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column("role", user_role_up, nullable=False, server_default="USER"),
    )
    op.execute("UPDATE users SET role = UPPER(role_tmp)")
    op.drop_column("users", "role_tmp")
    op.create_index("ix_users_role", "users", ["role"])
