"""Exercise image promotion with local Git and Docker command stubs."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/publish-latest.sh"


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.log = self.root / "docker-args"
        for name, body in {
            "git": (
                'test "$*" = "ls-remote --exit-code origin refs/heads/main" || exit 90\n'
                'test "$TEST_GIT_EXIT" = 0 || exit "$TEST_GIT_EXIT"\n'
                'printf "%s\\trefs/heads/main\\n" "$TEST_MAIN_SHA"\n'
            ),
            "docker": (
                'printf "%s\\n" "$@" > "$TEST_DOCKER_LOG"\n'
                'exit "$TEST_DOCKER_EXIT"\n'
            ),
        }.items():
            path = self.root / name
            path.write_text("#!/bin/sh\nset -eu\n" + body)
            path.chmod(0o755)
        self.environment = {
            "PATH": str(self.root) + os.pathsep + os.defpath,
            "IMAGE": "ghcr.io/example/proxy",
            "GITHUB_SHA": "a" * 40,
            "TEST_MAIN_SHA": "a" * 40,
            "TEST_GIT_EXIT": "0",
            "TEST_DOCKER_EXIT": "0",
            "TEST_DOCKER_LOG": str(self.log),
        }

    def run_publish(self):
        return subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=self.root,
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_current_main_is_promoted(self):
        result = self.run_publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.log.read_text().splitlines(),
            [
                "buildx", "imagetools", "create", "--tag",
                "ghcr.io/example/proxy:latest",
                "ghcr.io/example/proxy:" + "a" * 40,
            ],
        )

    def test_superseded_build_is_not_promoted(self):
        self.environment["TEST_MAIN_SHA"] = "b" * 40
        result = self.run_publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.log.exists())

    def test_remote_lookup_failure_blocks_promotion(self):
        self.environment["TEST_GIT_EXIT"] = "128"
        result = self.run_publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_registry_failure_fails_the_job(self):
        self.environment["TEST_DOCKER_EXIT"] = "1"
        self.assertNotEqual(self.run_publish().returncode, 0)

    def test_missing_publish_settings_block_promotion(self):
        valid = self.environment.copy()
        for key in ("IMAGE", "GITHUB_SHA"):
            for value in (None, ""):
                with self.subTest(setting=key, value=value):
                    self.environment = valid.copy()
                    if value is None:
                        del self.environment[key]
                    else:
                        self.environment[key] = value
                    result = self.run_publish()
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(key, result.stderr)
                    self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
