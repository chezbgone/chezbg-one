FROM golang:1.26-bookworm AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY main.go ./
COPY server ./server
RUN CGO_ENABLED=0 go build -o /out/rainbgone .

FROM gcr.io/distroless/static-debian12:nonroot
WORKDIR /app
COPY --from=build /out/rainbgone /usr/local/bin/rainbgone
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/rainbgone"]
