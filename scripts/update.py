"""Deploy newer main-branch releases of the apps present on this host."""

import fcntl
import json
import os
import re
import subprocess
import sys
from urllib.request import Request, urlopen


REPO = "chezbgone/chezbg-one"
ACTIONS = f"https://api.github.com/repos/{REPO}/actions"
APPS = {"rainbgone": "Build Rainbgone", "vodder-view": "Build Vodder View"}


def github_get(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "chezbg-one-update",
    }
    with urlopen(Request(f"{ACTIONS}/{path}", headers=headers), timeout=20) as response:
        return json.load(response), 'rel="next"' in response.headers.get("Link", "")


def latest_release(app):
    # The API's branch filter selects the hosting repo ref. The title records the app ref.
    main_titles = {
        f"{APPS[app]} from [{ref}] on refs/heads/main" for ref in ("main", "refs/heads/main")
    }
    runs = []
    page = 1
    while True:
        data, has_next = github_get(
            f"workflows/build-{app}.yml/runs?branch=main&exclude_pull_requests=true"
            f"&per_page=100&page={page}"
        )
        runs.extend(run for run in data["workflow_runs"] if run["display_title"] in main_titles)
        if not has_next:
            break
        page += 1

    for run in sorted(runs, key=lambda run: run["run_number"], reverse=True):
        run_id = run["id"]
        attempt = run["run_attempt"]
        if run["conclusion"] == "success":
            return run["created_at"], run_id, attempt
        # A failed or in-progress rerun can hide an earlier successful attempt.
        for previous in range(attempt - 1, 0, -1):
            data, _ = github_get(f"runs/{run_id}/attempts/{previous}")
            if data["conclusion"] == "success":
                return run["created_at"], run_id, previous
    return None


def deployed_tags(app):
    containers = subprocess.check_output(
        [
            "docker", "ps", "--all", "--quiet",
            "--filter", f"label=com.docker.compose.project={app}",
            "--filter", "label=com.docker.compose.oneoff=False",
        ],
        text=True,
    ).split()
    if not containers:
        return set()

    images = subprocess.check_output(
        ["docker", "inspect", "--type", "container", "--format", "{{.Config.Image}}", *containers],
        text=True,
    ).splitlines()
    prefix = re.escape(f"ghcr.io/{REPO}/{app}")
    tags = set()
    for image in images:
        match = re.fullmatch(rf"{prefix}-(?:backend|frontend):([1-9][0-9]*)-([1-9][0-9]*)", image)
        if not match:
            raise ValueError(f"cannot determine the deployed release from image {image!r}")
        tags.add(tuple(map(int, match.groups())))
    return tags


def update_app(app):
    deployed = deployed_tags(app)
    if not deployed:
        print(f"{app}: no deployment found, skipping", flush=True)
        return

    latest = latest_release(app)
    if latest is None:
        print(f"{app}: no successful main build with a recorded source ref", flush=True)
        return

    created_at, run_id, attempt = latest
    release = f"{run_id}-{attempt}"
    created_by_run = {run_id: created_at}
    for deployed_id, _ in deployed:
        if deployed_id not in created_by_run:
            run, _ = github_get(f"runs/{deployed_id}")
            created_by_run[deployed_id] = run["created_at"]
    deployed_releases = [
        (created_by_run[deployed_id], deployed_id, deployed_attempt)
        for deployed_id, deployed_attempt in deployed
    ]

    if min(deployed_releases) < latest and max(deployed_releases) <= latest:
        print(f"{app}: deploying {release}", flush=True)
        subprocess.run(["make", app, f"RELEASE={release}"], check=True)
    else:
        print(f"{app}: no newer main release (latest {release})", flush=True)


def main():
    # Serialize updates from this checkout even when both are started before a deploy finishes.
    directory = os.open(".", os.O_RDONLY)
    try:
        fcntl.flock(directory, fcntl.LOCK_EX)
        failed = False
        for app in APPS:
            try:
                update_app(app)
            except (OSError, subprocess.CalledProcessError, ValueError, KeyError) as error:
                print(f"{app}: update failed: {error}", file=sys.stderr)
                failed = True
        return int(failed)
    finally:
        os.close(directory)


if __name__ == "__main__":
    sys.exit(main())
