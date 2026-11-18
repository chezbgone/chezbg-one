# chezbg-one

Build and deployment configuration for apps under `*.chezbg.one` on one ARM64
server. GitHub Actions builds Rainbgone and Vodder View from their app repositories
and publishes the images to GHCR. The server runs those images with Docker Compose
and routes requests through Caddy.

## Build a release

Push the app version you want to build to GitHub. In this repo's **Actions** tab,
select the app's workflow and choose **Run workflow** on the hosting repo's
`main` branch. Leave `source_ref` at `main` to build the app's main branch, or
enter a tag or full commit SHA from the app repo. Builds triggered by a push to
the hosting repo also use the app's `main` branch.

For a private source repo, set the listed Actions secret to a token with read
access to that repo.

| App | Workflow | Private source secret |
| --- | --- | --- |
| Rainbgone | **Build Rainbgone** | `RAINBGONE_SOURCE_TOKEN` |
| Vodder View | **Build Vodder View** | `VODDER_VIEW_SOURCE_TOKEN` |

Each workflow publishes both images under a tag based on the run ID and attempt.
The successful run's summary shows the exact app commit and the deploy command.

## Set up the server

- Point the app's hostname (`rainbgone.chezbg.one` or `vods.chezbg.one`),
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
  editor at `/admin/players`. A fresh database starts with an empty roster.
  Confirm each player's consent before adding them through the roster editor.

## Deploy and roll back

Run `make proxy` on initial setup, or when changing the Caddyfile or proxy image.
Then run the command from the build summary, such as
`make vodder-view RELEASE=123456789-1`. The deploy pulls both images before
replacing either container, waits for the frontend to reach the backend, and
checks the public HTTPS route. To roll back, run the same command with the last
working release tag. Keep those image tags in GHCR.

After updating an app's credentials, redeploy its current release. Each deploy
recreates the app's containers so the backend reads the updated secrets file.
Expect a brief interruption during recreation.

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
build its images from a selectable source revision in Actions. Attach only its
public-facing HTTP service to the shared `caddy` network, using a unique network
alias. Add the hostname and upstream alias to `caddy/Caddyfile`, then reload
with `make proxy`. Keep other services on the app's own network.

Run `python3 -m unittest discover -s tests -v` to check the Compose files.
The tests work without a Docker daemon. Set `COMPOSE_COMMAND` to the standalone
Compose binary if needed.
