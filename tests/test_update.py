"""Exercise release selection without GitHub credentials or Docker."""

import subprocess
import unittest
from unittest.mock import call, patch

from scripts import update


def build(app, run_id, *, ref="main", host_ref="refs/heads/main", conclusion="success", attempt=1):
    return {
        "display_title": f"{update.APPS[app]} from [{ref}] on {host_ref}",
        "run_number": run_id,
        "id": run_id,
        "created_at": "2026-11-18T12:00:00Z",
        "conclusion": conclusion,
        "run_attempt": attempt,
    }


class UpdateTests(unittest.TestCase):
    def test_selects_successful_main_build_across_pages(self):
        app = "rainbgone"
        first_page = [
            build(app, 105, ref="fix-forecast"),
            build(app, 104, ref="refs/tags/main"),
            build(app, 103, host_ref="refs/tags/main"),
            build(app, 102, conclusion="failure"),
            dict(build(app, 101), display_title="Build Rainbgone"),
        ]
        successful = build(app, 100, ref="refs/heads/main")
        with patch.object(update, "github_get", side_effect=[
            ({"workflow_runs": first_page}, True),
            ({"workflow_runs": [successful]}, False),
        ]) as github:
            self.assertEqual(update.latest_release(app), (successful["created_at"], 100, 1))
        self.assertTrue(github.call_args.args[0].endswith("&page=2"))

    def test_failed_rerun_preserves_previous_successful_attempt(self):
        run = build("vodder-view", 100, conclusion="failure", attempt=3)
        with patch.object(update, "github_get", side_effect=[
            ({"workflow_runs": [run]}, False),
            ({"conclusion": "success"}, False),
        ]) as github:
            self.assertEqual(update.latest_release("vodder-view"), (run["created_at"], 100, 2))
        github.assert_called_with("runs/100/attempts/2")

    def test_update_only_deploys_the_app_with_a_newer_release(self):
        rainbgone = build("rainbgone", 101)
        vodder_view = build("vodder-view", 102)
        docker_output = [
            "rain-backend-id\nrain-frontend-id\n",
            "ghcr.io/chezbgone/chezbg-one/rainbgone-backend:100-1\n"
            "ghcr.io/chezbgone/chezbg-one/rainbgone-frontend:100-1\n",
            "vodder-backend-id\nvodder-frontend-id\n",
            "ghcr.io/chezbgone/chezbg-one/vodder-view-backend:102-1\n"
            "ghcr.io/chezbgone/chezbg-one/vodder-view-frontend:102-1\n",
        ]
        with (
            patch.object(update.subprocess, "check_output", side_effect=docker_output),
            patch.object(update.subprocess, "run") as deploy,
            patch.object(update, "github_get", side_effect=[
                ({"workflow_runs": [rainbgone]}, False),
                ({"created_at": "2026-11-17T12:00:00Z"}, False),
                ({"workflow_runs": [vodder_view]}, False),
            ]),
        ):
            self.assertEqual(update.main(), 0)
        deploy.assert_called_once_with(["make", "rainbgone", "RELEASE=101-1"], check=True)

    def test_partial_deploy_can_finish_but_a_newer_container_prevents_downgrade(self):
        for deployed, expected in [
            ({(100, 1), (100, 2)}, [call(["make", "vodder-view", "RELEASE=100-2"], check=True)]),
            ({(100, 1), (100, 3)}, []),
        ]:
            with (
                self.subTest(deployed=deployed),
                patch.object(update, "deployed_tags", return_value=deployed),
                patch.object(update, "latest_release", return_value=("2026-11-18T12:00:00Z", 100, 2)),
                patch.object(update.subprocess, "run") as deploy,
            ):
                update.update_app("vodder-view")
                self.assertEqual(deploy.call_args_list, expected)

    def test_skips_app_without_containers(self):
        with (
            patch.object(update.subprocess, "check_output", return_value=""),
            patch.object(update, "github_get") as github,
            patch.object(update.subprocess, "run") as deploy,
        ):
            update.update_app("rainbgone")
        github.assert_not_called()
        deploy.assert_not_called()

    def test_reports_failure_and_checks_other_app(self):
        with patch.object(
            update, "update_app", side_effect=[subprocess.CalledProcessError(1, "make"), None]
        ) as app:
            self.assertEqual(update.main(), 1)
        self.assertEqual(app.call_args_list, [call("rainbgone"), call("vodder-view")])
