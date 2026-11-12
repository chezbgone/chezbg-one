"""Check deployment contracts using Compose without a Docker daemon or secrets."""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        shutil.copyfile(ROOT / "compose.yaml", self.root / "compose.yaml")
        self.environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("COMPOSE_", "DOCKER_"))
            and key not in {"ACME_EMAIL", "CLOUDFLARE_API_KEY", "DOMAIN"}
        }
        self.values = {
            "ACME_EMAIL": "test@example.com",
            "CLOUDFLARE_API_KEY": "test_" + "x" * 35,
        }

    def compose(self):
        env_file = self.root / "test.env"
        env_file.write_text("".join(f"{key}={value}\n" for key, value in self.values.items()))
        command = shlex.split(os.environ.get("COMPOSE_COMMAND", "docker compose"))
        return subprocess.run(
            command
            + [
                "--env-file", str(env_file),
                "--project-name", "deployment-test",
                "-f", str(self.root / "compose.yaml"),
                "config", "--format", "json",
            ],
            cwd=self.root,
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def render(self):
        result = self.compose()
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_docker_socket_is_isolated_from_caddy_and_apps(self):
        model = self.render()
        caddy = model["services"]["caddy-proxy"]
        api = model["services"]["docker-socket-proxy"]
        self.assertEqual(caddy["environment"]["DOCKER_HOST"], "tcp://docker-socket-proxy:2375")
        self.assertFalse(any(volume["type"] == "bind" for volume in caddy["volumes"]))
        self.assertFalse(api.get("ports"))
        self.assertEqual(set(api["networks"]), {"docker-api"})
        self.assertTrue(model["networks"]["docker-api"]["internal"])
        self.assertEqual(set(caddy["networks"]), {"caddy", "docker-api"})
        self.assertEqual(caddy["depends_on"]["docker-socket-proxy"]["condition"], "service_healthy")
        self.assertEqual(api["volumes"][0]["source"], "/var/run/docker.sock")
        self.assertTrue(api["volumes"][0]["read_only"])
        self.assertEqual(api["environment"]["POST"], "0")
        enabled = {key for key, value in api["environment"].items() if value == "1"}
        self.assertEqual(enabled, {"CONTAINERS", "EVENTS", "INFO", "NETWORKS", "PING", "VERSION"})


if __name__ == "__main__":
    unittest.main()
