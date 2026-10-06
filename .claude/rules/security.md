# Security rules (project)

> Generic security baseline (validate input, ORM only, no secrets in logs, pin deps, least
> privilege) is inherited from `~/.claude/CLAUDE.md`. This file records the
> **project-specific** security model. Full detail: `docs/architecture/security.md` and
> `docs/architecture/auth.md`.

- **Multi-tenancy is application-level**: every query MUST filter by `user_id`. There is no
  PostgreSQL RLS yet (planned Phase 4) — a missing `user_id` filter is a data-leak bug.
- **Use SQLAlchemy exclusively** — no raw/string-built SQL. JSONB fields need explicit casts
  if raw SQL is ever unavoidable.
- **Auth**: bcrypt password hashing (auto salt); JWT access (30 min) + refresh (7 days),
  Bearer in the `Authorization` header.
- **Mailbox credentials are Fernet-encrypted at rest** (`ENCRYPTION_KEY`). Decrypt only at
  point of use; never log decrypted credentials or tokens.
- No secrets in code, logs, error messages, or client bundles.
- Security is every agent's job; the `security-auditor` agent is the backstop at review time.
