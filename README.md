# chezbg-one

Shared ingress for everything hosted under `*.chezbg.one` on a single host,
plus the per-project deployment overlays. Each app lives in its own repo and
stays deployment-agnostic; this repo owns hostnames, TLS, and routing.

## Layout

    compose.yaml            # shared Caddy proxy + restricted Docker socket proxy
    Dockerfile              # builds Caddy w/ cloudflare DNS + docker-proxy plugins
    .github/workflows/      # CI builds the proxy image (arm64) + pushes to GHCR
    .env                    # CLOUDFLARE_API_KEY + ACME_EMAIL (gitignored; copy from .env.example)
    Makefile                # one target per project
    projects/
      vodder-view.yaml      # deployment overlay (host, TLS, routing)
      vodder-view.env       # DOMAIN=...
      rainbgone.yaml
      rainbgone.env

The app repos are expected as siblings of this one (`../vodder-view`,
`../rainbgone`); override with `make <target> APPS=/path/to/apps`.

## One-time setup

1. `cp .env.example .env`, then fill in both values (the file is gitignored, so
   neither lands in the repo):
   - `CLOUDFLARE_API_KEY` — a Cloudflare API **token** with both **Zone → DNS → Edit**
     and **Zone → Zone → Read**, scoped to the `chezbg.one` zone. The DNS provider
     needs zone read access to find the zone before creating challenge records.
     This token is shared by every project's DNS-01 challenge.
   - `ACME_EMAIL` — your Let's Encrypt contact address for renewal-failure notices.
2. Point DNS at the host's Elastic IP — a wildcard is simplest:
   `*.chezbg.one  A  <elastic-ip>` (set it DNS-only / grey-cloud, not proxied).

## Usage

    make proxy          # create the `caddy` network + start the proxy (idempotent)
    make vodder-view    # build + deploy vodder-view
    make rainbgone      # build + deploy rainbgone

Start or update the proxy before deploying apps. The Cloudflare token is passed
only to Caddy's environment; app labels use the literal runtime placeholder
`cloudflare {env.CLOUDFLARE_API_KEY}`. After changing the token in `.env`, run
`make proxy` to recreate Caddy with the new value. App deployment commands load
only their per-project domain file.
Compose rejects missing or empty proxy credentials, contact email, or app domain
before starting services. `make proxy` also validates before creating its network.

## Adding a project

1. In the app repo, add a clean `compose.prod.yaml` (build + run only — no host
   ports, no Caddy labels, no domain).
2. Here, add `projects/<name>.yaml` (overlay) and `projects/<name>.env` (DOMAIN).
   In the overlay, expose only the public-facing service: put it on the `caddy`
   network, `caddy.import: common`, `caddy.tls.dns: cloudflare {env.CLOUDFLARE_API_KEY}`,
   and `caddy.reverse_proxy`. Keep the runtime placeholder literal so the token
   stays out of application labels.
   If a service also needs to reach siblings, re-list its private (`appnet`) network too
   (setting `networks:` replaces, not appends).
3. Add a `make <name>` target mirroring the others.
   Use `${DOMAIN:?Set DOMAIN in the project environment file}` for the hostname
   label so an unset or empty domain fails before deployment.

Distinct subdomains are the only thing you have to keep unique now — no host
ports are published by any project, so they never collide.

## Docker API access

Caddy discovers containers through `docker-socket-proxy`, which allows only
read requests for containers, networks, events, daemon information, ping, and
version negotiation. Docker API writes and other endpoint groups are denied.
Only the socket proxy mounts the host Docker socket. Its API is on a private,
internal network shared with Caddy, with no published port or application access.
This configuration supports standalone Docker Compose, rather than Docker Swarm.

Run the configuration regression checks with Docker Compose installed; the
checks use temporary files and dummy credentials and do not require a daemon:

    python3 -m unittest discover -s tests -v

Set `COMPOSE_COMMAND=/path/to/docker-compose` to use a standalone Compose CLI.

## Proxy image

The Caddy proxy is **not** built on the host — compiling it with `xcaddy`
exhausts a nano instance's memory. Instead, GitHub Actions builds it natively on
an arm64 runner and pushes to `ghcr.io/chezbgone/chezbg-one:latest`
(public package). `make proxy` just pulls and runs it.

Caddy and both plugins are pinned to explicit versions in the `Dockerfile`.
Review and update those versions together when upgrading the proxy.

Edits to the `Dockerfile` rebuild and republish automatically on push to `main`;
trigger a manual rebuild from the Actions tab (`workflow_dispatch`). To pick up a
new image on the host: `make proxy`.

CI checks the deployment configuration before building. Concurrent runs on the
same ref cancel older runs. Images are first published with their commit SHA;
only a build that still matches the head of `main` is promoted to `latest`.
Pull requests run validation without publishing images.
