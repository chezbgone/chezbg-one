# chezbg-one

Build and deployment configuration for apps under `*.chezbg.one` on one ARM64
server. GitHub Actions builds each app from its source repository and publishes
the images to GHCR. The server runs those images with Docker Compose and routes
requests through Caddy.

## Deploy an app update

1. Push your changes to `main` in the app's GitHub repo.
2. From the `chezbg-one` checkout, run the command for the app you're updating.

   ```bash
   gh workflow run build-rainbgone.yml --ref main
   gh workflow run build-vodder-view.yml --ref main
   ```

   You can also open **Actions** in GitHub, select the app's build workflow,
   choose **Run workflow**, and select `main` as the workflow branch. Both methods
   build the app's `main` branch by default.

3. Wait for the workflow to succeed. The run summary shows the app commit it built.
4. On the server, run `make update` from the `chezbg-one` checkout.

`make update` requires Python 3. It updates each app already deployed from this
repo that has a newer successful `main` build. To deploy an app for the first
time, update only one app, or use a build from another source ref, see
[Deploy a specific release](#deploy-a-specific-release).

### Build options

To build a specific revision, set `source_ref` to a branch, tag, or full commit
SHA from the app repo. With the CLI, add `-f source_ref=YOUR_REF` and keep
`--ref main` so the workflow publishes the images. Builds triggered by a push
to the hosting repo use the app's `main` branch.

For a private source repo, set the Actions secret referenced in the app's build
workflow to a token with read access to the source repo. [Build workflows](.github/workflows)

Each workflow publishes both images under a tag based on the run ID and attempt.
The successful run's summary gives the deploy command for that tag. The updater
reads the public `chezbg-one` workflow runs without a GitHub token and uses the
source ref recorded in each run name to identify `main` builds.

## Set up the server

- Find the app's hostname in the Caddy configuration. Point that hostname or a
  wildcard DNS record at the server's public address. Allow inbound TCP 80 and 443
  so Caddy can obtain certificates. UDP 443 is optional for HTTP/3.
  [Caddy configuration](caddy/Caddyfile)
- Install Docker with Compose, `make`, and `curl`. Check out this repo on the
  server. For private GHCR packages, log in to `ghcr.io` with read access to
  the packages before deploying.
- Copy `secrets/<app>.env.example` to `secrets/<app>.env` and fill in the app's
  credentials. See the app's own docs for configuration details. Give `secrets/`
  mode `0700` to protect it on the host and keep the file readable by the
  backend container's non-root user (mode `0644`).
- Run `make proxy` on initial setup and whenever you change the Caddyfile or
  proxy image.

## Deploy a specific release

On the server, run the deploy command from the successful workflow's summary
in the `chezbg-one` checkout. The deploy pulls the app's images before replacing
its containers, waits for the app to pass its health checks, and checks the
public HTTPS route. After an app's first deploy, `make update` can update it.

To roll back, run the same command with the last working release tag. Keep those
image tags in GHCR.

After updating an app's credentials, redeploy its current release. Each deploy
recreates the app's containers so the backend reads the updated secrets file.
Expect a brief interruption during recreation.

Keep app data volumes across deploys. For backups, find the data volume in the
app's production Compose file at `projects/<app>/compose.yaml` and follow the
app's backup instructions.

## Add another app

Add its build recipe and production Compose file under `projects/<app>/` and
build its images from a selectable source revision in Actions. Attach only its
public-facing HTTP service to the shared `caddy` network, using a unique network
alias. Add the hostname and upstream alias to `caddy/Caddyfile`, then reload
with `make proxy`. Keep other services on the app's own network.

Run `python3 -m unittest discover -s tests -v` to check the Compose files.
The tests work without a Docker daemon. Set `COMPOSE_COMMAND` to the standalone
Compose binary if needed.
