# chezbg-one — shared ingress proxy + per-project deployment overlays.
#
# APPS points at the directory where your app repos are checked out,
# relative to this file. Override on the CLI if they live elsewhere:
#   make vodder-view APPS=/srv/apps
APPS ?= ..

.PHONY: proxy vodder-view rainbgone

# Bring up (or update) the shared Caddy proxy. Safe to re-run.
proxy:
	docker network create --ipv6 caddy 2>/dev/null || true
	docker compose up -d --build

# Each app target layers the app's clean prod base (FIRST, so relative
# build paths resolve against the app repo) with this repo's overlay,
# and injects the global secret (.env) + per-project domain (projects/*.env).
vodder-view:
	docker compose \\
	  -f $(APPS)/vodder-view/compose.prod.yaml \\
	  -f projects/vodder-view.yaml \\
	  --env-file .env --env-file projects/vodder-view.env \\
	  -p vodder-view up -d --build

rainbgone:
	docker compose \\
	  -f $(APPS)/rainbgone/compose.prod.yaml \\
	  -f projects/rainbgone.yaml \\
	  --env-file .env --env-file projects/rainbgone.env \\
	  -p rainbgone up -d --build
