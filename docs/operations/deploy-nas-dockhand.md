# Deploy to a NAS with Dockhand (LAN / HTTP)

This guide deploys Subscription Tracker to a NAS using [Dockhand](https://dockhand.pro/)
(a self-hosted Docker management UI). The stack runs on plain HTTP on the LAN; when you
expose it on a public domain, TLS is terminated **upstream** (Cloudflare Tunnel or your
NAS reverse proxy).

Files used:
- `deploy/nas/docker-compose.nas.yml` — the stack (no Traefik; frontend nginx also proxies `/api`).
- `deploy/nas/.env.nas.example` — the environment template.

## How it works (vs production)

The production `docker-compose.prod.yml` relies on an external **Traefik** to route
`/api → backend` and `/ → frontend` and to terminate TLS. A NAS usually has no Traefik, so
the NAS stack instead reconfigures the **frontend nginx** (via an inline Compose `config`) to
proxy `/api` to the backend. The result: one HTTP port serves the whole app.

```
Browser --HTTPS--> [Cloudflare Tunnel / NAS reverse proxy]   (TLS here)
                              |
                        http://<NAS_IP>:8080
                              |
                     frontend (nginx)
                      /  (SPA)     \  /api -> backend:8000
```

Images are pulled from GHCR, built automatically by `.github/workflows/cd.yml` on every push
to `main` (`ghcr.io/ankirama/subtracker-backend` and `-frontend`, tag `latest`).

## Prerequisites

- Dockhand installed on the NAS. Docker Compose **v2.23.1+** (needed for the inline nginx
  `config`; check with `docker compose version`). Older Docker → see [Fallback](#fallback-older-docker-compose).
- Ports 80/443 free on the NAS only if you also run a reverse proxy there.

## Step 1 — Make the GHCR images pullable

By default GHCR packages are **private**. Pick one:

**Option A — make them public (simplest).** On GitHub → your profile → *Packages* →
`subtracker-backend` → *Package settings* → *Change visibility* → **Public**. Repeat for
`subtracker-frontend`. No NAS login needed.

**Option B — keep them private, log in from the NAS.** Create a GitHub Personal Access Token
(classic) with scope `read:packages`. In Dockhand → *Registries* (or *Settings → Registries*)
add `ghcr.io` with your GitHub username and the token as password. Dockhand will then pull the
private images.

> Not sure which they are? Try Option A; if the packages don't appear under your profile yet,
> push to `main` once so the CD workflow publishes them, then set visibility.

## Step 2 — Create the stack in Dockhand

1. Dockhand → *Stacks* → *New Stack*. Name it `subtracker`.
2. Paste the contents of `deploy/nas/docker-compose.nas.yml` into the Compose editor.
3. Open the **Environment** tab and paste every key from `deploy/nas/.env.nas.example`,
   filling in real values:
   - `POSTGRES_PASSWORD` — a strong password.
   - `JWT_SECRET_KEY` — `openssl rand -hex 32`.
   - `ENCRYPTION_KEY` — `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
   - `OPENAI_API_KEY` — your key.
   - `FRONTEND_PORT` — the LAN port to expose (default `8080`).
   - `CORS_ORIGINS` — your public domain (and the `http://<NAS_IP>:8080` LAN origin while testing).
   - `GITHUB_REPOSITORY` — `ankirama/subtracker` (lowercase), `IMAGE_TAG` — `latest`.
4. Deploy. On first start the `migrate` service runs `alembic upgrade head`, then postgres,
   redis, backend, celery worker/beat and frontend come up.

## Step 3 — Create the first admin user

The app has no default admin. After the stack is healthy, open a shell into the **backend**
container from Dockhand (*Containers → subtracker_backend → Exec/Console*) and run:

```bash
python -m scripts.create_admin --email admin@example.com --password 'a-strong-password' --name 'Admin'
```

## Step 4 — Access it

- **On the LAN**: `http://<NAS_IP>:8080`.
- **Public domain**: point a **Cloudflare Tunnel** (or your NAS reverse proxy) at
  `http://<NAS_IP>:8080`. TLS is handled by the tunnel/proxy — the stack stays HTTP.
  Make sure the domain is in `CORS_ORIGINS`.

## Updating

When you push to `main`, CD rebuilds the `latest` images. To roll the NAS forward:
Dockhand → stack `subtracker` → **Pull** (re-pull images) → **Redeploy**. The `migrate`
service re-runs `alembic upgrade head` automatically each deploy.

To pin a specific build instead of `latest`, set `IMAGE_TAG` to a tag the CD workflow
produced (e.g. `main-<sha>`).

## Backups

Postgres data lives in the `postgres_data` named volume; a `./backups` folder in the stack
directory is mounted into postgres and backend. Use the repo's `scripts/backup.sh` /
`scripts/restore.sh` patterns, or Dockhand's built-in volume backup (to S3/SFTP/B2), to
snapshot `postgres_data` on a schedule.

## Troubleshooting

- **`/api` returns 404 or the login call fails** — the frontend nginx `config` didn't apply.
  Confirm Docker Compose ≥ v2.23.1 (`docker compose version`); otherwise use the fallback below.
- **`ImagePullBackOff` / pull denied** — GHCR images are private and Dockhand has no
  credentials (Step 1, Option B), or `GITHUB_REPOSITORY` is wrong/not lowercase.
- **Backend restarts / DB connection errors** — check `POSTGRES_*` match between the postgres
  service and the constructed `DATABASE_URL`; wait for the `migrate` service to finish first.
- **`env file .env not found`** — make sure the Environment tab is filled; Dockhand writes it
  to the stack's `.env`. If your Dockhand version doesn't, add a `.env` file to the stack
  directory manually (SSH) with the same keys.

### Fallback (older Docker Compose)

If `configs.content` isn't supported, drop the `configs:` block and the frontend's
`configs:` list, place a `nginx.nas.conf` file (same server block as in the compose) next to
the compose on the NAS, and bind-mount it instead:

```yaml
  frontend:
    volumes:
      - ./nginx.nas.conf:/etc/nginx/conf.d/default.conf:ro
```
