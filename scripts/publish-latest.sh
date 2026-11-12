#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE:?IMAGE is required}"
: "${GITHUB_SHA:?GITHUB_SHA is required}"

# A rerun of an old main build may start after a newer build. Keep its SHA
# image available, but only the current main commit may become latest.
main_sha="$(git ls-remote --exit-code origin refs/heads/main | cut -f1)"
if [[ "$main_sha" != "$GITHUB_SHA" ]]; then
    echo "Skipping latest: this commit is no longer the head of main."
    exit 0
fi

docker buildx imagetools create --tag "${IMAGE}:latest" "${IMAGE}:${GITHUB_SHA}"
