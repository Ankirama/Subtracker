---
description: Restart a docker-compose service and tail its logs for 30 seconds
argument-hint: <service> (default: backend)
---

# /restart-and-tail

Restart a docker-compose service and watch its logs for 30 seconds, surfacing errors/warnings.

## Steps

1. **Resolve service**
   - If no `<service>` argument, default to `backend`.
   - Validate the service exists in `docker-compose.dev.yml` (grep `services:` block).

2. **Restart**
   - Run: `docker compose -f docker-compose.dev.yml restart <service>`
   - On failure, surface the error and stop.

3. **Tail logs for ~30s**
   - Run with timeout: `timeout 30 docker compose -f docker-compose.dev.yml logs -f --tail=50 <service>` (or use `gtimeout` on macOS without coreutils).
   - On macOS where `timeout` is missing, fall back to: open the logs in background, sleep 30, kill the log process. Provide a one-liner that works.

4. **Report**
   - Filter the captured output for lines matching `(?i)error|warn|exception|traceback`.
   - If matches are found, print them grouped by severity.
   - If no matches, print: `[clean] no errors or warnings detected in 30s`.

## Notes

- Do not interpret routine startup messages (e.g., "Application startup complete") as warnings.
- The 30s window is heuristic; if the service is still starting, the result may be inconclusive — say so.
