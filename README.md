# chezbg-one

Shared ingress for everything hosted under `*.chezbg.one` on a single host,
plus the per-project deployment overlays. Each app lives in its own repo and
stays deployment-agnostic; this repo owns hostnames, TLS, and routing.

## Layout

    compose.yaml            # the shared Caddy proxy (caddy-docker-proxy)
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
   - `CLOUDFLARE_API_KEY` — a Cloudflare API **token** (Zone:DNS:Edit on the
     chezbg.one zone), shared by every project's DNS-01 challenge.
   - `ACME_EMAIL` — your Let's Encrypt contact address for renewal-failure notices.
2. Point DNS at the host's Elastic IP — a wildcard is simplest:
   `*.chezbg.one  A  <elastic-ip>` (set it DNS-only / grey-cloud, not proxied).

## Usage

    make proxy          # create the `caddy` network + start the proxy (idempotent)
    make vodder-view    # build + deploy vodder-view
    make rainbgone      # build + deploy rainbgone

## Adding a project

1. In the app repo, add a clean `compose.prod.yaml` (build + run only — no host
   ports, no Caddy labels, no domain).
2. Here, add `projects/<name>.yaml` (overlay) and `projects/<name>.env` (DOMAIN).
   In the overlay, expose only the public-facing service: put it on the `caddy`
   network, `caddy.import: common`, set `caddy.tls.dns` and `caddy.reverse_proxy`.
   If a service also needs to reach siblings, re-list its private (`appnet`) network too
   (setting `networks:` replaces, not appends).
3. Add a `make <name>` target mirroring the others.

Distinct subdomains are the only thing you have to keep unique now — no host
ports are published by any project, so they never collide.

## Proxy image

The Caddy proxy is **not** built on the host — compiling it with `xcaddy`
exhausts a nano instance's memory. Instead, GitHub Actions builds it natively on
an arm64 runner and pushes to `ghcr.io/chezbgone/chezbg-one:latest`
(public package). `make proxy` just pulls and runs it.

Edits to the `Dockerfile` rebuild and republish automatically on push to `main`;
trigger a manual rebuild from the Actions tab (`workflow_dispatch`). To pick up a
new image on the host: `make proxy`.
