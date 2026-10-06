# Environment & secrets

> Generic secret hygiene lives in `~/.claude/CLAUDE.md`. This file records the
> **project-specific** environment contract.

- `.env` is **never committed** (gitignored). Committed templates: `.env.example` (dev),
  `.env.production.example`, `deploy/nas/.env.nas.example` (NAS). Add any new variable to
  the relevant templates and document it.
- All configuration comes from environment variables via `backend/app/config.py`
  (pydantic-settings, reads `.env`); nothing hardcoded.
- **Vite**: only `VITE_`-prefixed variables reach the browser. Never put a secret in one.
- **Docker**: inject env at runtime (`env_file` / compose); never bake secrets into images.

## Required variables (no default in `config.py` — startup fails without them)
`DATABASE_URL`, `REDIS_URL`, `OPENAI_API_KEY`, `JWT_SECRET_KEY`, `ENCRYPTION_KEY`,
`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`.
`CORS_ORIGINS` has a localhost default. Optional with defaults: OpenAI rate limits,
confidence-routing thresholds (`DEFAULT_CONFIDENCE_*`), Resend, Google OAuth, `REQUIRE_INVITE_TOKEN`.

- `ENCRYPTION_KEY` is a Fernet key — generate with:
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- `JWT_SECRET_KEY` — generate with `openssl rand -hex 32`.
- VAPID keys — `backend/scripts/generate_vapid_keys.py`.

## Known gaps (follow-ups, checked 2026-10-06 — don't fix opportunistically)
- `.env.example` lacks the `VAPID_*` keys (required!), `RESEND_*`, `GOOGLE_*`,
  `REQUIRE_INVITE_TOKEN` and `FRONTEND_URL`; the production/NAS templates have them.
- Insecure defaults in `config.py`: `DEBUG=True`, `RESEND_API_KEY="test_key"`. Production
  must set them explicitly; new required settings must have **no** default (fail fast).
