# chezbg-one

Build and deployment configuration for apps under `*.chezbg.one` on one ARM64
server. GitHub Actions builds Rainbgone and Vodder View from pinned source commits
and publishes their images to GHCR. The server runs those images with Docker
Compose and routes requests through Caddy.

## Build a release

Make sure the app's source commit is available on GitHub, then update its pin
and push the hosting repo to `main`. Run the app's workflow manually on `main`
to rebuild the current pin. For a private source repo, set the listed Actions
secret to a token with read access to that repo.

| App | Workflow | Pin location | Private source secret |
| --- | --- | --- | --- |
| Rainbgone | **Build Rainbgone** | `.github/workflows/build.yml` | `RAINBGONE_SOURCE_TOKEN` |
| Vodder View | **Build Vodder View** | `.github/workflows/build-vodder-view.yml` | `VODDER_VIEW_SOURCE_TOKEN` |

Each workflow publishes both images under a tag based on the run ID and attempt.
The successful run's summary gives the deploy command.

## Set up the server

- Point the app's hostname (`rainbgone.chezbg.one` or `vodder-view.chezbg.one`),
  or a wildcard DNS record, at the server's public address. Allow inbound TCP
  80 and 443 so Caddy can obtain certificates.
  UDP 443 is optional for HTTP/3.
- Install Docker with Compose, `make`, and `curl`. Check out this repo on the
  server. For private GHCR packages, log in to `ghcr.io` with read access to
  the packages before deploying.
- Copy `secrets/rainbgone.env.example` to `secrets/rainbgone.env` and fill in the
  Pirate Weather key. Give `secrets/` mode `0700` to protect it on the host and
  keep the file readable by the backend container's non-root user (mode `0644`).
- Copy `secrets/vodder-view.env.example` to `secrets/vodder-view.env` and fill in the
  HenrikDev and Twitch credentials. Set `ADMIN_PASSWORD` to enable the roster
  editor at `/admin/players`. A fresh database starts syncing Zander at startup.
  Confirm his consent before the first deploy.

## Deploy and roll back

Run `make proxy` on initial setup, or when changing the Caddyfile or proxy image.
Then run the command from the build summary, such as
`make vodder-view RELEASE=123456789-1`. The deploy pulls both images before
replacing either container, waits for the frontend to reach the backend, and
checks the public HTTPS route. To roll back, run the same command with the last
working release tag. Keep those image tags in GHCR.

Vodder View keeps its roster and match history in the `vodder-view_data` volume.
Keep that volume across deploys. For a backup, stop the backend and copy the
entire data directory, including any SQLite sidecar files.

If migrating Rainbgone from the previous setup, first build a release and copy the old
Rainbgone backend `.env` to `secrets/rainbgone.env` with the permissions above.
Run the new commands from the existing proxy checkout so Compose reuses Caddy's
data volume and removes the old socket proxy. Run `make proxy` followed by the
app deploy. Expect a brief interruption while the proxy and app are replaced.
The old Cloudflare token and proxy `.env` are no longer used.

## Add another app

Add its build recipe and production Compose file under `projects/<app>/` and
build its images from a pinned source revision in Actions. Attach only its
public-facing HTTP service to the shared `caddy` network, using a unique network
alias. Add the hostname and upstream alias to `caddy/Caddyfile`, then reload
with `make proxy`. Keep other services on the app's own network.

Run `python3 -m unittest discover -s tests -v` to check the Compose files.
The tests work without a Docker daemon. Set `COMPOSE_COMMAND` to the standalone
Compose binary if needed.
