# MailGuard-AI — Database Layer

This directory contains everything related to the database layer:

| File / Folder | Purpose |
|---------------|---------|
| `schema.sql` | MySQL 8 DDL — full schema for all 8 tables. |
| `er_diagram.md` | ER diagram (Mermaid) and relationship notes. |
| `../backend/app/database/connection.py` | SQLAlchemy engine & session factory. |
| `../backend/app/database/seed.py` | Seeds admin user + default model version. |
| `../backend/alembic/` | Migrations (Alembic). |
| `../backend/alembic/versions/0001_initial.py` | Initial migration mirroring `schema.sql`. |

## Quick Start

### 1. Create the MySQL database

```bash
mysql -u root -p < schema.sql
```

This creates the `mailguard_ai` database with all tables, indexes and constraints.

### 2. Configure environment

Copy `../backend/.env.example` to `../backend/.env` and edit the values:

```dotenv
DB_HOST=localhost
DB_PORT=3306
DB_NAME=mailguard_ai
DB_USER=mailguard
DB_PASSWORD=your_password_here
```

### 3. Run Alembic migrations (recommended)

```bash
cd ../backend
alembic upgrade head
```

### 4. (Alternative) Auto-create tables in dev mode

```bash
cd ../backend
python -c "from app.database.connection import init_db; init_db()"
```

### 5. Seed initial data

```bash
cd ../backend
python -m app.database.seed
```

This creates:
- One admin user (`admin@mailguard.ai` / `ChangeMe123!`).
- One default model version (`v1.0.0-baseline`, marked active).

## Tables Overview

| Table | Purpose |
|-------|---------|
| `users` | Registered users (with role: `user` / `admin`). |
| `emails` | Captured email content + metadata. |
| `predictions` | AI predictions per email (class, confidence, risk, explanation). |
| `feedback` | User feedback for predictions (Human-in-the-loop). |
| `whitelist` | Trusted senders per user. |
| `blacklist` | Suspicious senders per user. |
| `model_versions` | Registry of trained AI model versions. |
| `activity_logs` | Audit trail for important actions. |

See `er_diagram.md` for the full diagram and relationship details.