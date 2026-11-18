# chezbg-one

Build and deployment configuration for apps under `*.chezbg.one` on one ARM64
server. GitHub Actions builds Rainbgone from a pinned source commit and publishes
its images to GHCR. The server runs those images with Docker Compose and routes
requests through Caddy. The app repo supplies source and dependency lockfiles.

## Build a release

Make sure the Rainbgone source commit is available on GitHub, then update the pin
in `.github/workflows/build.yml` and push to `main`. Run **Build Rainbgone**
manually on `main` to rebuild the current pin.
For a private source repo, set `RAINBGONE_SOURCE_TOKEN` in this repo's Actions
secrets to a token with read access to the source. The workflow publishes both
images under a tag based on the run ID and attempt and prints the deploy command
in the successful run's summary.

## Set up the server

- Point `rainbgone.chezbg.one` or a wildcard DNS record at the server's public
  address. Allow inbound TCP 80 and 443 so Caddy can obtain certificates.
  UDP 443 is optional for HTTP/3.
- Install Docker with Compose, `make`, and `curl`. Check out this repo on the
  server. For private GHCR packages, log in to `ghcr.io` with read access to
  the packages before deploying.
- Copy `secrets/rainbgone.env.example` to `secrets/rainbgone.env` and fill in the
  Pirate Weather key. Give `secrets/` mode `0700` to protect it on the host and
  keep the file readable by the backend container's non-root user (mode `0644`).

## Deploy and roll back

Run `make proxy` on initial setup, or when changing the Caddyfile or proxy image.
Then run the command from the build summary, for example
`make rainbgone RELEASE=123456789-1`. The deploy pulls both images before
replacing either container, waits for the frontend to reach the backend, and
checks the public HTTPS route. To roll back, run the same command with the last
working release tag. Keep those image tags in GHCR.

If replacing the previous setup, first build a release and copy the old
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
