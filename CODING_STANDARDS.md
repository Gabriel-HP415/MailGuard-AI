# ============================================
# MailGuard-AI — Coding Standards
# ============================================

## 1. Architecture Principles
- **Clean Architecture** — Separate concerns: API → Controllers → Services → Repositories → Database.
- **SOLID Principles** — Single responsibility, Open/closed, Liskov substitution, Interface segregation, Dependency inversion.
- **Repository Pattern** — All DB access goes through repositories. No raw queries in services.
- **Service Layer** — Business logic lives in services, not in routes or repositories.
- **Dependency Injection** — Use FastAPI's `Depends` for clean wiring.

## 2. Folder Responsibilities
- `api/` — Route definitions only (thin).
- `controllers/` — Request/response orchestration.
- `services/` — Business logic (pure functions where possible).
- `repositories/` — DB CRUD operations.
- `models/` — SQLAlchemy ORM models.
- `schemas/` — Pydantic request/response models.
- `middlewares/` — Auth, CORS, rate-limit, error handlers.
- `core/` — Configuration, security, constants.
- `utils/` — Helpers, decorators.

## 3. Naming Conventions
- Files & folders: `snake_case`
- Classes: `PascalCase`
- Functions & variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- DB tables: `snake_case`, plural (`users`, `predictions`)
- API endpoints: `kebab-case` paths, JSON keys `snake_case`

## 4. Python Style
- Follow **PEP 8**.
- Use **type hints** everywhere.
- Maximum line length: **100 characters**.
- Docstrings for all public classes and functions (Google style).
- Use `pydantic.BaseModel` for I/O validation.
- Use `enum.Enum` for fixed value sets (e.g. `EmailClass`).

## 5. JavaScript / Extension Style
- ES6+ modules.
- `const`/`let` only (no `var`).
- Async/await for promises.
- ESLint with Airbnb base config.

## 6. Git Workflow
- Branch naming: `feature/<scope>`, `fix/<scope>`, `docs/<scope>`.
- Commit messages: `type(scope): summary` (conventional commits).
- One PR per logical change.

## 7. Testing
- `pytest` for backend (unit + integration).
- Coverage target: **≥ 70%** on `services/` and `repositories/`.
- Every new service must include unit tests.

## 8. Documentation
- Every module has a short docstring explaining its purpose.
- Public API must be in `docs/api.md`.
- Diagrams in Mermaid format (rendered automatically on GitHub).

## 9. Security
- Never commit secrets. Use `.env` and load via `pydantic-settings`.
- Always hash passwords with **bcrypt**.
- Validate all inputs via Pydantic.
- Apply rate limiting on all public endpoints.