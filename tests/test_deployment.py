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
        (self.root / "projects").mkdir()
        shutil.copyfile(ROOT / "projects/rainbgone.yaml", self.root / "projects/rainbgone.yaml")
        # Minimal deployment-agnostic app base, like the sibling app repo.
        (self.root / "app.yaml").write_text(
            "services:\n"
            "  frontend:\n"
            "    image: example/frontend:test\n"
            "    networks: [appnet]\n"
            "  backend:\n"
            "    image: example/backend:test\n"
            "    networks: [appnet]\n"
            "networks:\n"
            "  appnet: {}\n"
        )
        self.environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("COMPOSE_", "DOCKER_"))
            and key not in {"ACME_EMAIL", "CLOUDFLARE_API_KEY", "DOMAIN"}
        }
        self.values = {
            "ACME_EMAIL": "test@example.com",
            "CLOUDFLARE_API_KEY": "test_" + "x" * 35,
            "DOMAIN": "app.example.com",
        }

    def compose(self, files=("compose.yaml",)):
        env_file = self.root / "test.env"
        env_file.write_text("".join(f"{key}={value}\n" for key, value in self.values.items()))
        command = shlex.split(os.environ.get("COMPOSE_COMMAND", "docker compose"))
        file_args = [arg for name in files for arg in ("-f", str(self.root / name))]
        return subprocess.run(
            command
            + [
                "--env-file", str(env_file),
                "--project-name", "deployment-test",
                *file_args,
                "config", "--format", "json",
            ],
            cwd=self.root,
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def render(self, files=("compose.yaml",)):
        result = self.compose(files)
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

    def test_dns_token_is_kept_out_of_application_metadata(self):
        proxy = self.render()["services"]["caddy-proxy"]
        token = self.values["CLOUDFLARE_API_KEY"]
        self.assertEqual(proxy["environment"]["CLOUDFLARE_API_KEY"], token)
        self.assertNotIn(token, json.dumps(proxy["labels"]))

        # The app should render successfully without access to the DNS token.
        del self.values["CLOUDFLARE_API_KEY"]
        app = self.render(("app.yaml", "projects/rainbgone.yaml"))
        self.assertNotIn(token, json.dumps(app))
        frontend = app["services"]["frontend"]
        self.assertEqual(frontend["labels"]["caddy.tls.dns"], "cloudflare {env.CLOUDFLARE_API_KEY}")
        self.assertEqual(set(frontend["networks"]), {"appnet", "caddy"})
        self.assertEqual(set(app["services"]["backend"]["networks"]), {"appnet"})

    def test_missing_proxy_settings_are_rejected(self):
        valid = self.values.copy()
        for key in ("ACME_EMAIL", "CLOUDFLARE_API_KEY"):
            for value in (None, ""):
                with self.subTest(setting=key, value=value):
                    self.values = valid.copy()
                    if value is None:
                        del self.values[key]
                    else:
                        self.values[key] = value
                    result = self.compose()
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(key, result.stderr)

    def test_missing_application_domain_is_rejected(self):
        for value in (None, ""):
            with self.subTest(value=value):
                if value is None:
                    del self.values["DOMAIN"]
                else:
                    self.values["DOMAIN"] = value
                result = self.compose(("app.yaml", "projects/rainbgone.yaml"))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("DOMAIN", result.stderr)


if __name__ == "__main__":
    unittest.main()
