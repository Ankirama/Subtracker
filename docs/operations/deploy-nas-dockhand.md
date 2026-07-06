# Deploy to a NAS with Dockhand (behind a reverse proxy)

This guide deploys Subscription Tracker to a NAS using [Dockhand](https://dockhand.pro/)
(a self-hosted Docker management UI). The stack speaks plain HTTP internally and is exposed
through a reverse proxy on the same NAS — **Nginx Proxy Manager (NPM)** in this guide — which
terminates TLS. The frontend is **not** published on the LAN; NPM reaches it over a shared
Docker network by container name.

Files used:
- `deploy/nas/docker-compose.nas.yml` — the stack (no Traefik; frontend nginx also proxies `/api`).
- `deploy/nas/.env.nas.example` — the environment template.

## How it works (vs a Traefik server setup)

A typical Traefik-based server setup relies on an external **Traefik** to route
`/api → backend` and `/ → frontend` and to terminate TLS. A NAS usually has no Traefik, so
the NAS stack instead reconfigures the **frontend nginx** (via an inline Compose `config`) to
proxy `/api` to the backend. One container then serves the whole app, and your NAS reverse
proxy sits in front of it.

```
Browser --HTTPS--> Nginx Proxy Manager        (TLS / Let's Encrypt here)
                        |  (shared `proxy` Docker network)
                subtracker_frontend:80 (nginx)
                 /  (SPA)       \  /api -> backend:8000
```

Images are pulled from GHCR, built automatically by `.github/workflows/cd.yml` on every push
to `main` (`ghcr.io/ankirama/subtracker-backend` and `-frontend`, tag `latest`).

## Prerequisites

- Dockhand installed on the NAS. Docker Compose **v2.23.1+** (needed for the inline nginx
  `config`; check with `docker compose version`). Older Docker → see [Fallback](#fallback-older-docker-compose).
- A reverse proxy on the NAS (this guide uses Nginx Proxy Manager) with ports 80/443.
- A shared Docker network named `proxy` that both NPM and this stack join. Create it once —
  Dockhand → *Networks → Create* (name `proxy`), or `docker network create proxy`.
- UGREEN DXP4800: it's an x86-64 box, so the `linux/amd64` GHCR images run natively — no
  multi-arch build needed.
- All persistent data is bind-mounted under **`DATA_PATH`** (default `./data` in the stack dir).
  Set `DATA_PATH` to an absolute path (e.g. `/volume2/docker/subtracker`) to store it on a chosen
  volume. It **must** be on **local storage** (not an SMB/NFS share) — Postgres corrupts on network
  filesystems.
- Services run as `PUID:PGID` (default `1000:100`, the UGREEN "users" group) so the data files are
  owned by your NAS user, not root. Because they run **non-root**, you must **pre-create the data
  dirs and chown them** before the first deploy — SSH into the NAS and run (substitute your
  `DATA_PATH`; the default is the `data/` subdir of the stack directory):
  ```bash
  DATA_PATH=/volume2/docker/subtracker   # or ./data inside the stack dir
  mkdir -p "$DATA_PATH"/{postgres,redis,backups,logos,logs}
  chown -R 1000:100 "$DATA_PATH"
  ```
  (The frontend is the one exception — nginx runs as root to bind port 80 and stores nothing.)

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
   - `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` — **required** (the backend won't start without
     them): `npx web-push generate-vapid-keys`.
   - `CORS_ORIGINS` and `FRONTEND_URL` — your public https domain (e.g. `https://subtracker.example.com`).
   - `GITHUB_REPOSITORY` — `ankirama/subtracker` (lowercase), `IMAGE_TAG` — `latest`.
   - Optional per feature: Google OAuth (`GOOGLE_CLIENT_ID` / `_SECRET` / `_REDIRECT_URI`) and
     email (`RESEND_*`). See the notes in `.env.nas.example`.
4. **If you use Google (Gmail) OAuth**: in Google Cloud Console → *APIs & Services →
   Credentials → your OAuth client*, add the exact redirect URI
   `https://<your-domain>/api/oauth/google/callback` under *Authorized redirect URIs*, and make
   sure `GOOGLE_REDIRECT_URI` matches it.
5. Make sure the shared `proxy` network exists (see Prerequisites), then deploy. On first
   start the `migrate` service runs `alembic upgrade head`, then postgres, redis, backend,
   celery worker/beat and frontend come up.

## Step 3 — Create the first admin user

The app has no default admin. After the stack is healthy, open a shell into the **backend**
container from Dockhand (*Containers → subtracker_backend → Exec/Console*) and run:

```bash
python -m scripts.create_admin --email admin@example.com --password 'a-strong-password' --name 'Admin'
```

## Step 4 — Expose with Nginx Proxy Manager

The frontend has no published port; NPM reaches it over the shared `proxy` network.

1. **Connect NPM to the `proxy` network.** In the NPM stack add the external network to the
   NPM app service, then redeploy NPM:
   ```yaml
   services:
     app:            # the jc21/nginx-proxy-manager service
       networks: [default, proxy]
   networks:
     proxy:
       external: true
   ```
   (Or, in Dockhand → the NPM container → *Networks*, attach `proxy`.)
2. **Add a proxy host.** NPM UI → *Hosts → Proxy Hosts → Add Proxy Host*:
   - **Domain Names**: your public domain (e.g. `subtracker.example.com`).
   - **Scheme** `http`, **Forward Hostname** `subtracker_frontend`, **Forward Port** `80`.
   - Toggle **Block Common Exploits** and **Websockets Support** ON.
   - **SSL** tab: request a new Let's Encrypt certificate, then enable **Force SSL** + **HTTP/2**.
   - **Advanced** tab (only if large exports/uploads fail with 413): `client_max_body_size 25m;`.
3. Confirm `CORS_ORIGINS` (Step 2) contains that https origin; redeploy the stack if you changed it.

> Prefer a published LAN port instead of a reverse proxy? Add
> `ports: ["${FRONTEND_PORT:-8080}:80"]` to the frontend service, drop the `proxy` network,
> set `FRONTEND_PORT`, and point any proxy at `http://<NAS_IP>:<FRONTEND_PORT>`.

## Step 5 — Verify

Browse to `https://<your-domain>` — the login page should load. Open
`https://<your-domain>/docs`: the FastAPI UI confirms the nginx `/api` proxy is wired end to end.

## Updating

When you push to `main`, CD rebuilds the `latest` images. To roll the NAS forward:
Dockhand → stack `subtracker` → **Pull** (re-pull images) → **Redeploy**. The `migrate`
service re-runs `alembic upgrade head` automatically each deploy.

To pin a specific build instead of `latest`, set `IMAGE_TAG` to a tag the CD workflow
produced (e.g. `main-<sha>`).

## Automatic PostgreSQL backups

The stack ships a `pg_backup` sidecar
([prodrigestivill/postgres-backup-local](https://github.com/prodrigestivill/docker-postgres-backup-local))
that runs a scheduled logical `pg_dump` and prunes old dumps. Backups are written gzipped to
`$DATA_PATH/backups/` (default `./data/backups/`), organized into `last/`, `daily/`, `weekly/`,
`monthly/`.

> **Why not just copy the `postgres_data` volume?** Copying the live data directory while
> Postgres is running can capture an inconsistent (corrupt) snapshot. A `pg_dump` is
> transaction-consistent and restores cleanly — so this is what runs by default.

Tune it from the Environment tab:
- `BACKUP_SCHEDULE` — `@daily` (default), `@hourly`, `@weekly`, or a cron expr like `0 3 * * *`.
- `BACKUP_KEEP_DAYS` / `BACKUP_KEEP_WEEKS` / `BACKUP_KEEP_MONTHS` — retention.

### Notifications (Discord)

Set `DISCORD_WEBHOOK_URL` to get a message on every backup — green ✅ on success, red ❌ on
failure. A hook script (`/hooks/discord-notify`, mounted by the stack) fires on the sidecar's
`post-backup` and `error` events; leave the variable blank to disable.

1. In Discord: *Server Settings → Integrations → Webhooks → New Webhook*, pick a channel,
   **Copy Webhook URL**.
2. Paste it as `DISCORD_WEBHOOK_URL` in the stack Environment and redeploy.
3. Test it: exec into `subtracker_pg_backup` and run
   `sh /hooks/discord-notify post-backup "manual test"` to send a sample success message; or
   trigger a real dump with `backup.sh` and watch the channel.

The notification is best-effort (a failed webhook never breaks the backup).

### Get the backups off the NAS

The dumps live at `$DATA_PATH/backups/` (default `./data/backups/`, e.g.
`/volume2/docker/subtracker/backups/`), so they're directly visible on the NAS. For an offsite
copy, either point **Dockhand's** scheduled backup at a remote target (S3 / SFTP / B2), or have
UGOS's own backup app sync that folder.

### Restore

Dumps use `--clean --if-exists`, so they drop and recreate objects. Stop `backend`,
`celery_worker` and `celery_beat` first to avoid writes during the restore, then exec into
`subtracker_pg_backup` (it has `psql` and the credentials) and load a dump:

```bash
# list available dumps
ls -lh /backups/daily/

# restore one (adjust the filename)
zcat /backups/daily/<db>-<timestamp>.sql.gz \
  | psql "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@postgres:5432/$POSTGRES_DB"
```

Restart the stopped services afterwards. To verify backups are running, check the
`subtracker_pg_backup` container logs — each run logs the dump it wrote.

## Troubleshooting

- **`/api` returns 404 or the login call fails** — the frontend nginx `config` didn't apply.
  Confirm Docker Compose ≥ v2.23.1 (`docker compose version`); otherwise use the fallback below.
- **`ImagePullBackOff` / pull denied** — GHCR images are private and Dockhand has no
  credentials (Step 1, Option B), or `GITHUB_REPOSITORY` is wrong/not lowercase.
- **`network proxy declared as external, but could not be found`** — create it before
  deploying: `docker network create proxy` (or Dockhand → *Networks*).
- **NPM shows `502 Bad Gateway`** — NPM isn't on the `proxy` network (Step 4.1), the stack
  isn't healthy yet, or the Forward Hostname/Port aren't `subtracker_frontend` / `80`.
- **Backend restarts / DB connection errors** — check `POSTGRES_*` match between the postgres
  service and the constructed `DATABASE_URL`; wait for the `migrate` service to finish first.
- **`migrate` exits 1 with `pydantic ... ValidationError ... Field required`** — a required
  setting is missing from the loaded `.env`. `app.config` is validated at import time, so every
  container needs the full set. Most often it's `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` (they
  have no defaults) — add them to the `.env`. (`REDIS_URL` / `CELERY_*` are injected by the
  compose, so they don't need to be in `.env`.)
- **API calls 307-redirect and the SPA shows "Failed to load ..."** — the `https` scheme wasn't
  reaching the backend, so it built `http://` redirects the browser blocks. The compose fixes
  this: nginx forwards NPM's `X-Forwarded-Proto`, and uvicorn runs with `--proxy-headers
  --forwarded-allow-ips '*'`. Make sure you're on the latest compose and redeployed. (NPM sends
  `X-Forwarded-Proto: https` by default, so no NPM change is needed.)
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
