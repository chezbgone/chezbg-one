ARG CADDY_VERSION=2.11.4

# --- build stage: compile Caddy with the plugins we need ---
#   caddy-docker-proxy   -> reads caddy.* labels off containers (config mechanism)
#   caddy-dns/cloudflare -> DNS-01 ACME challenge for wildcard/grey-cloud certs
FROM caddy:${CADDY_VERSION}-builder AS builder

RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare \
    --with github.com/lucaslorentz/caddy-docker-proxy/v2

# --- runtime stage ---
FROM caddy:${CADDY_VERSION}-alpine

COPY --from=builder /usr/bin/caddy /usr/bin/caddy

CMD ["caddy", "docker-proxy"]
