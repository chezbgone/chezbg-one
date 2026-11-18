"""Render production Compose files without a daemon or real credentials."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP = "projects/rainbgone/compose.yaml"


class DeploymentTests(unittest.TestCase):
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
        self.assertEqual(secret["source"], str(ROOT / "secrets/rainbgone.env"))
        self.assertEqual(secret["target"], "/app/.env")
        self.assertTrue(secret["read_only"])
        self.assertFalse(secret["bind"]["create_host_path"])

    def test_missing_release_is_rejected(self):
        result = self.compose(APP)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set RELEASE", result.stderr)
