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

## Step 4 — Access it on the LAN

Browse to `http://<NAS_IP>:<FRONTEND_PORT>` (e.g. `http://192.168.1.50:8080`). Confirm the
login page loads and that a request to `/api/...` works (open `/docs` — it should show the
FastAPI UI, proving the nginx `/api` proxy is wired). Then expose it publicly (Step 5).

> UGREEN DXP4800 note: it's an x86-64 box, so the `linux/amd64` GHCR images run natively —
> no multi-arch build needed. If port `8080` clashes with a UGOS service, set `FRONTEND_PORT`
> to something free (e.g. `8090`).

## Step 5 — Expose publicly with Nginx Proxy Manager

NPM terminates TLS (Let's Encrypt) and proxies to the frontend. Pick one wiring:

### Option A — shared Docker network (recommended, no LAN port exposed)

Put NPM and the frontend on the same Docker network so NPM reaches the container by name,
and the app is never published on the LAN.

1. Create a shared network once (Dockhand → *Networks → Create*, or `docker network create proxy`).
2. In the **NPM** stack, add that network to the NPM app service:
   ```yaml
   services:
     app:            # the jc21/nginx-proxy-manager service
       networks: [default, proxy]
   networks:
     proxy:
       external: true
   ```
3. In `docker-compose.nas.yml`, add the same external network to the **frontend** service and
   declare it (you can then drop the `ports:` mapping — NPM reaches it internally):
   ```yaml
   services:
     frontend:
       networks: [internal, proxy]
       # ports: []            # optional: remove to keep it off the LAN entirely
   networks:
     proxy:
       external: true
   ```
4. NPM → *Proxy Hosts → Add*: **Forward Hostname** `subtracker_frontend`, **Forward Port** `80`,
   **Scheme** `http`.

### Option B — via the published LAN port (simplest)

Keep the `ports: "${FRONTEND_PORT}:80"` mapping. In NPM → *Proxy Hosts → Add*:
**Forward Hostname** `<NAS_IP>`, **Forward Port** `<FRONTEND_PORT>` (e.g. `8080`), **Scheme** `http`.

### NPM proxy-host settings (both options)

- **Domain Names**: your public domain (e.g. `subtracker.example.com`).
- Toggle **Block Common Exploits** and **Websockets Support** ON.
- **SSL** tab: request a new Let's Encrypt certificate, then enable **Force SSL** and **HTTP/2**.
- **Advanced** tab (only if large exports/uploads fail with 413): add
  `client_max_body_size 25m;`.

Finally, set `CORS_ORIGINS` to the **https** public origin (e.g. `https://subtracker.example.com`)
in the stack Environment and redeploy. The SPA calls `/api` same-origin, so this is belt-and-braces.

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
