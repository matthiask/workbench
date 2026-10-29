from unittest.mock import patch

from django.test import TestCase

from workbench import cli_version, factories


class CLIVersionTest(TestCase):
    def test_versions(self):
        """Outdated CLIs are told to upgrade, too old ones are rejected"""
        self.client.force_login(factories.UserFactory.create())

        with (
            patch.object(cli_version, "MINIMUM", (0, 2, 0)),
            patch.object(cli_version, "LATEST", "0.3.0"),
        ):
            response = self.client.get("/api/me/")
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("X-Workbench-CLI-Latest", response)

            response = self.client.get("/api/me/", headers={"X-Workbench-CLI": "0.2.1"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["X-Workbench-CLI-Latest"], "0.3.0")

            response = self.client.get("/api/me/", headers={"X-Workbench-CLI": "0.1.9"})
            self.assertEqual(response.status_code, 426)
            self.assertIn("uv tool upgrade workbench-cli", response.json()["detail"])

            response = self.client.get(
                "/api/me/", headers={"X-Workbench-CLI": "nonsense"}
            )
            self.assertEqual(response.status_code, 426)

    def test_latest(self):
        """The latest version is the one in the repository"""
        self.assertRegex(cli_version.LATEST, r"^\d+\.\d+\.\d+$")
