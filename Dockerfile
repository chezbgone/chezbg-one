FROM alpine:3.22.0

RUN apk add --no-cache curl

RUN curl -L -o /usr/local/bin/caddy \
    "https://caddyserver.com/api/download?os=linux&arch=arm64&p=github.com%2Fcaddy-dns%2Fcloudflare&p=github.com%2Flucaslorentz%2Fcaddy-docker-proxy%2Fv2" \
    && chmod +x /usr/local/bin/caddy

CMD ["caddy", "docker-proxy"]

