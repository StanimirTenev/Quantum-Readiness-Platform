# Public Demo Deployment

Operator runbook for putting the `public` Compose profile (see `infra/docker/README.md`) on a
real VPS with a real domain -- pre-flight checklist, firewall guidance, a walkthrough script for
actually giving the demo, and how to reset it back to a clean state. This is the operational
companion to `infra/docker/README.md`'s "Exposing this outside a trusted local network" section
(read that first for how the mechanism itself works); this file is about running it on a real
box in front of real people.

## Pre-flight checklist

- [ ] Docker + Docker Compose v2 installed on the VPS (`docker compose version`).
- [ ] DNS: the domain (or subdomain, e.g. `demo.example.com`) has an A/AAAA record pointing at
      the VPS's public IP. Confirm with `dig +short demo.example.com` from a machine that isn't
      the VPS itself -- Let's Encrypt will fail otherwise, and it fails *after* Caddy is already
      up, so check this before deploying, not after.
- [ ] `infra/docker/.env` exists (copied from `.env.example`) with real, non-default values:
      - `DOMAIN` set to the real domain above.
      - `POSTGRES_PASSWORD` changed from the `qrp` default.
      - `QRP_API_KEY` set if this is an operator-walkthrough demo (see the "Which mode" note
        below), or left unset if `QRP_DEMO_MODE` is doing the gating instead.
      - `QRP_DEMO_MODE=true` set if this instance will be left running unattended for visitors
        to click around on their own (see `services/api-gateway/README.md`).
      - `CORS_ALLOW_ORIGINS` set to `https://<the real domain>`.
- [ ] Ports 80 and 443 are free on the VPS (nothing else already bound to them).
- [ ] The repo is on the VPS (`git clone`/`git pull`) at whatever path you'll run
      `docker compose` from.

**Which mode**: `QRP_API_KEY` and `QRP_DEMO_MODE` are independent (see
`services/api-gateway/README.md`) -- pick based on who's using the instance:
- Giving a live, attended walkthrough yourself → `QRP_API_KEY`, no `QRP_DEMO_MODE`. You control
  the console directly; nothing needs blocking since you're not inviting arbitrary input.
- Leaving it up for visitors to click around unattended → `QRP_DEMO_MODE=true`, with or without
  `QRP_API_KEY`. Blocks arbitrary scan ingest / mutations regardless of whether a visitor has a
  key.
- Both together works too (a key-gated demo that's *also* mutation-safe) -- not mutually
  exclusive.

## Firewall

`api-gateway` (8000) and `web-ui` (5173) are bound to `127.0.0.1` in `docker-compose.yml`, not
`0.0.0.0` -- they are not listening on any externally-reachable interface at all, regardless of
firewall state. A firewall rule "blocking" those ports would be redundant; they're already
unreachable at the socket level. The firewall's actual job here is narrower:

- [ ] Restrict SSH sensibly (key-only auth, consider `ufw limit 22/tcp` for brute-force
      throttling) -- this is the VPS's real attack surface, not the QRP ports.
- [ ] Allow 80/tcp and 443/tcp (Caddy's HTTP->HTTPS redirect + the ACME challenge need 80; the
      actual demo traffic needs 443):
  ```bash
  sudo ufw allow 22/tcp
  sudo ufw allow 80/tcp
  sudo ufw allow 443/tcp
  sudo ufw enable
  sudo ufw status verbose
  ```
- [ ] **Known gotcha, don't rely on ufw alone**: Docker manipulates `iptables` directly (the
      `DOCKER-USER` chain) for any port a container publishes to `0.0.0.0`, which can bypass
      ufw's own `INPUT` chain rules entirely. This doesn't matter for `api-gateway`/`web-ui`
      (loopback-bound, not published to `0.0.0.0` in the first place -- see above) but it does
      mean a *future* change that publishes a new port to `0.0.0.0` could end up reachable even
      with a ufw "deny" rule in place. Verify what's actually externally reachable after any
      compose-file change, don't just trust the firewall config:
  ```bash
  # From a machine that is NOT the VPS:
  nmap -Pn -p 22,80,443,8000,5173,5432 <vps-ip>   # only 22/80/443 should show open
  ```

## Deploy

```bash
cd infra/docker
docker compose --profile public up -d --build
```

Watch it come up healthy, then confirm from outside the VPS:

```bash
curl -I https://<your-domain>/health
```

## Operator demo script

A walkthrough for giving the live demo (attended, `QRP_API_KEY` mode) or for what a visitor
sees (unattended, `QRP_DEMO_MODE` mode) -- same click order either way:

1. Open `https://<your-domain>`. If `QRP_API_KEY` is set, paste it into the **API Key** field
   and click **Check** -- the "CONNECTED" pill confirms it. If `QRP_DEMO_MODE` is on, point out
   the yellow banner across the top ("Public demo mode...").
2. **Dashboard tab** → click **Load Demo**. Talk through the step table as it seeds host,
   network, repo, and vendor-document evidence, then point at the new **Executive Summary**
   panel (assets assessed, risk breakdown, Wave 1 count, recommended action) as the
   one-paragraph version of "here's what this run found."
3. **Assets tab** → click any row (they're all rated critical in the demo dataset by design) →
   walk through **Asset detail**: the **Recommended Next Action** callout first (the single
   concrete next step), then Risk Narrator's plain-language explanation, then the full Change
   Assistant checklist, then the colour-coded wave badge.
4. **Migration Plan tab** → show the Wave 1/2/3 breakdown (colour-coded the same way) and the
   vendor readiness context.
5. **Copilot tab** → ask a free-text question (e.g. "what crypto dependencies did we discover?")
   to show the deterministic Q&A layer -- mention no external LLM call is ever made.
6. **Reports tab** → click **Generate workspace report** to show the full persisted operator
   report rendering inline (Executive Summary through Technical Appendix -- see
   `tools/report/build_operator_report.py`).

## Resetting the demo data

`QRP_DEMO_MODE` blocks arbitrary ingest, so the dataset can't drift beyond repeated (idempotent,
no-op) "Load Demo" clicks -- there's normally nothing to clean up. To force a genuinely clean
slate anyway (e.g. before a big presentation, or to recover from a weird state):

```bash
cd infra/docker
docker compose --profile public down -v
docker compose --profile public up -d --build
```

Then click **Load Demo** again (or `curl -X POST https://<domain>/api/demo/load`) to reseed.

**Verified gotcha, always include `--profile public` on `down`/`down -v`**: leaving off the
flag doesn't stop `caddy` -- Compose simply doesn't see a service gated behind a profile it
wasn't told is active, so `caddy` (and its `caddy-data`/`caddy-config` volumes) are silently
left running/orphaned instead of torn down, and the network removal fails with "resource is
still in use." Confirmed live: `docker compose down -v` (no profile flag) after starting with
`--profile public` left `docker-caddy-1` running and both Caddy volumes un-removed; re-running
with `--profile public down -v` cleaned it up correctly. If you ever see a leftover
`docker-caddy-1` after a reset, this is why -- `docker ps -a` to check, `docker compose
--profile public down -v` to actually clean it up.
