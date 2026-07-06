# Environment & secrets

> Generic secret hygiene lives in `~/.claude/CLAUDE.md`. This file records the
> **project-specific** environment contract.

- `.env` is **never committed** (gitignored). `.env.example` lists **every** key with a
  placeholder and is committed — add any new variable to it and document it.
- All configuration comes from environment variables; nothing hardcoded. The app should
  fail fast on a missing required variable.
- **Vite**: only `VITE_`-prefixed variables reach the browser. Never put a secret in one.
- **Docker**: inject env at runtime (`env_file` / compose); never bake secrets into images.

## Required variables
`DATABASE_URL`, `REDIS_URL`, `OPENAI_API_KEY`, `JWT_SECRET_KEY`, `ENCRYPTION_KEY`,
`CORS_ORIGINS`. (See `.env.example` for the full set incl. Celery, OpenAI rate limits,
and confidence-routing thresholds.)

- `ENCRYPTION_KEY` is a Fernet key — generate with:
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- `JWT_SECRET_KEY` — generate with `openssl rand -hex 32`.
