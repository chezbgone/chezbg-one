# chezbg-one — shared ingress proxy + per-project deployment overlays.
#
# APPS points at the directory where your app repos are checked out,
# relative to this file. Override on the CLI if they live elsewhere:
#   make rainbgone APPS=/srv/apps
APPS ?= ..

.PHONY: proxy rainbgone

# Bring up (or update) the shared Caddy proxy. Safe to re-run.
# Image is built in CI and pulled from GHCR (see .github/workflows/build.yml),
# so the host never compiles Caddy locally.
proxy:
	docker network create --ipv6 caddy 2>/dev/null || true
	docker compose pull
	docker compose up -d

# Each app target layers the app's clean prod base (FIRST, so relative
# build paths resolve against the app repo) with this repo's overlay,
# and injects the global secret (.env) + per-project domain (projects/*.env).
rainbgone:
	docker compose \
	  -f $(APPS)/rainbgone/compose.prod.yaml \
	  -f projects/rainbgone.yaml \
	  --env-file .env --env-file projects/rainbgone.env \
	  -p rainbgone up -d --pull always
