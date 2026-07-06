# Common Gotchas

Practical traps to avoid when working in this codebase. The most safety-critical ones
(multi-tenancy `user_id` filtering, Fernet credential decryption) are also enforced as
always-on rules in `.claude/rules/security.md`.

## Email processing
- JMAP uses provider-specific email IDs — don't assume a format.
- HTML emails need BeautifulSoup parsing; French date formats vary — the AI handles them.
- PayPal emails need special duplicate handling (see `docs/architecture/deduplication.md`).
- `subscriptions.custom_label` differentiates same-provider subs (e.g. Twitch streamers).
- `email_processing_records.extracted_data` is JSONB with raw extraction results.

## Database
- **Always filter by `user_id`** for multi-tenancy.
- Encrypted credentials must be decrypted before use (Fernet, key from `ENCRYPTION_KEY`).
- JSONB fields need explicit casting in raw SQL.
- Run `alembic heads` if you suspect a migration conflict.

## Docker
- Volume mounts enable hot-reload.
- DB persists in named volume `postgres_data`.
- Restart the backend container after dependency installs.
- Common port collisions: 5173 (frontend), 8000 (backend), 5432 (Postgres), 6379 (Redis).

## Frontend
- React Query caches 30s by default.
- WebSocket reconnection logic is needed for job progress updates.
- Chakra UI requires a `ThemeProvider` wrapper.
