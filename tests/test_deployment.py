"""Check production deployment configuration without a daemon or credentials."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP = "projects/rainbgone/compose.yaml"
VODDER_VIEW = "projects/vodder-view/compose.yaml"


class DeploymentTests(unittest.TestCase):
    def deploy_commands(self, app):
        result = subprocess.run(
            ["make", "--dry-run", "--no-print-directory", app, "RELEASE=12345-1"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return [shlex.split(line) for line in result.stdout.splitlines()]

    def test_rainbgone_deploy_checks_forecast_page_after_redirect(self):
        curl = next(command for command in self.deploy_commands("rainbgone") if command[0] == "curl")
        self.assertIn("--location", curl)
        self.assertIn("--fail", curl)
        self.assertGreater(int(curl[curl.index("--max-time") + 1]), 20)

    def test_redeploy_recreates_app_containers_after_pulling_images(self):
        for app in ("rainbgone", "vodder-view"):
            with self.subTest(app=app):
                commands = self.deploy_commands(app)
                compose = ["docker", "compose", "-f", f"projects/{app}/compose.yaml"]
                pull = [*compose, "pull"]
                up = next(command for command in commands if command[:5] == [*compose, "up"])
                self.assertIn("--force-recreate", up)
                self.assertIn("--wait", up)
                self.assertLess(commands.index(pull), commands.index(up))

    def compose(self, file, release=""):
        command = shlex.split(os.environ.get("COMPOSE_COMMAND", "docker compose"))
        return subprocess.run(
            [*command, "--env-file", os.devnull, "-f", file, "config", "--format", "json"],
            cwd=ROOT,
            env={"PATH": os.environ["PATH"], "RELEASE": release},
            capture_output=True,
            text=True,
            timeout=30,
        )

    def render(self, file, release=""):
        result = self.compose(file, release)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_only_caddy_publishes_ports_and_uses_no_docker_socket(self):
        proxy = self.render("compose.yaml")["services"]
        self.assertEqual(set(proxy), {"caddy-proxy"})
        caddy = proxy["caddy-proxy"]
        self.assertEqual({port["published"] for port in caddy["ports"]}, {"80", "443"})
        bind_sources = {volume["source"] for volume in caddy["volumes"] if volume["type"] == "bind"}
        self.assertEqual(bind_sources, {str(ROOT / "caddy")})

    def test_app_stack_runs_from_one_release_with_private_backend(self):
        services = self.render(APP, "12345-1")["services"]
        for service in services.values():
            self.assertTrue(service["image"].endswith(":12345-1"))
            self.assertFalse(service.get("ports"))
            self.assertNotIn("build", service)
        self.assertEqual(set(services["backend"]["networks"]), {"appnet"})
        frontend = services["frontend"]
        self.assertEqual(frontend["networks"]["caddy"]["aliases"], ["rainbgone-frontend"])
        self.assertIn("reverse_proxy rainbgone-frontend:3000", (ROOT / "caddy/Caddyfile").read_text())
        secret = services["backend"]["volumes"][0]
        self.assertEqual(secret["type"], "bind")
        self.assertEqual(secret["source"], str(ROOT / "secrets/rainbgone.env"))
        self.assertEqual(secret["target"], "/app/.env")
        self.assertTrue(secret["read_only"])

    def test_vodder_view_routes_through_frontend_and_preserves_history(self):
        stack = self.render(VODDER_VIEW, "12345-1")
        services = stack["services"]
        for role, service in services.items():
            self.assertEqual(
                service["image"], f"ghcr.io/chezbgone/chezbg-one/vodder-view-{role}:12345-1"
            )
            self.assertFalse(service.get("ports"))
            self.assertNotIn("build", service)

        backend, frontend = services["backend"], services["frontend"]
        self.assertEqual(set(backend["networks"]), {"appnet"})
        self.assertEqual(backend["networks"]["appnet"]["aliases"], ["vodderview-backend"])
        self.assertEqual(frontend["networks"]["caddy"]["aliases"], ["vodder-view-frontend"])
        self.assertRegex(
            (ROOT / "caddy/Caddyfile").read_text(),
            r"(?m)^vods\.chezbg\.one \{[^}]*\breverse_proxy vodder-view-frontend:80$",
        )
        self.assertIn("/api/health", frontend["healthcheck"]["test"][-1])
        self.assertEqual(backend["environment"]["ADMIN_ORIGIN"], "https://vods.chezbg.one")
        self.assertEqual(backend["environment"]["DATABASE_PATH"], "/data/vodder-view.sqlite")

        mounts = {volume["target"]: volume for volume in backend["volumes"]}
        secret = mounts["/app/.env"]
        self.assertEqual(backend["command"], ["-env", "/app/.env"])
        self.assertEqual(secret["type"], "bind")
        self.assertEqual(secret["source"], str(ROOT / "secrets/vodder-view.env"))
        self.assertTrue(secret["read_only"])
        self.assertEqual(mounts["/data"]["type"], "volume")
        self.assertEqual(mounts["/data"]["source"], "data")
        self.assertEqual(stack["volumes"]["data"]["name"], "vodder-view_data")

    def test_missing_release_is_rejected(self):
        for app in (APP, VODDER_VIEW):
            with self.subTest(app=app):
                result = self.compose(app)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Set RELEASE", result.stderr)
