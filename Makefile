.PHONY: proxy rainbgone

# Compose uses this tag for both app images.
export RELEASE

proxy:
	docker network inspect caddy >/dev/null 2>&1 || docker network create --ipv6 caddy
	docker compose -f compose.yaml pull
	docker compose -f compose.yaml up --wait --wait-timeout 60 --remove-orphans
	docker compose -f compose.yaml exec -T caddy-proxy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile

rainbgone:
	test -f secrets/rainbgone.env || (echo 'Create secrets/rainbgone.env from its example.' >&2; exit 1)
	docker compose -f projects/rainbgone/compose.yaml pull
	docker compose -f projects/rainbgone/compose.yaml up --pull never --wait --wait-timeout 60
	curl --fail --silent --show-error --output /dev/null --retry 8 --retry-all-errors --retry-delay 3 --max-time 8 https://rainbgone.chezbg.one/
