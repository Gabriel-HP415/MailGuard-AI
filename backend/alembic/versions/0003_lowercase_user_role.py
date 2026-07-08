"""Fix enum casing to match Python enum `values`.

Revision ID: 0003_lowercase_user_role
Revises: 0002_firebase_fields
Create Date: 2026-07-05 21:30:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "0003_lowercase_user_role"
down_revision = "0002_firebase_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use raw SQL for PostgreSQL enum conversion
    # Step 1: Drop default to remove dependency
    op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")

    # Step 2: Change column to VARCHAR
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(20) USING role::text")

    # Step 3: Update values to lowercase
    op.execute("UPDATE users SET role = LOWER(role) WHERE role IS NOT NULL")

    # Step 4: Drop old enum type
    op.execute("DROP TYPE IF EXISTS user_role")

    # Step 5: Create new enum type with lowercase values
    op.execute("CREATE TYPE user_role AS ENUM ('user', 'admin')")

    # Step 6: Change column to new enum type
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE user_role USING role::user_role")

    # Step 7: Set default
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'user'")

    # Step 8: Create index
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)")


def downgrade() -> None:
    # Step 1: Drop default
    op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")

    # Step 2: Change to VARCHAR
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(20) USING role::text")

    # Step 3: Update values to uppercase
    op.execute("UPDATE users SET role = UPPER(role) WHERE role IS NOT NULL")

    # Step 4: Drop old enum
    op.execute("DROP TYPE IF EXISTS user_role")

    # Step 5: Create new enum with uppercase
    op.execute("CREATE TYPE user_role AS ENUM ('USER', 'ADMIN')")

    # Step 6: Change to new enum
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE user_role USING role::user_role")

    # Step 7: Set default
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'USER'")

    # Step 8: Create index
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)")
