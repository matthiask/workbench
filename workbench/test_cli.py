import datetime as dt
import re
import tempfile
import threading
import types
import urllib.parse
import urllib.request
from pathlib import Path
from unittest.mock import patch

import wb
from click.testing import CliRunner
from django.test import Client, TestCase
from django.test.utils import override_settings
from django.utils.translation import deactivate_all
from rich.console import Console

from workbench import cli_version, factories
from workbench.accounts.features import FEATURES, F
from workbench.accounts.models import APIToken
from workbench.offers.models import Offer
from workbench.tools.validation import in_days, monday


class Response:
    """The parts of a requests response the CLI uses"""

    def __init__(self, response):
        self.status_code = response.status_code
        self.ok = response.status_code < 400
        self.headers = response.headers
        self.text = response.content.decode()
        self._response = response

    def json(self):
        return self._response.json()


class CLITest(TestCase):
    """Runs the real CLI against the API, requests go through the test client"""

    def setUp(self):
        self.api_client = Client()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        for patcher in [
            patch.object(wb.requests, "request", self.request),
            patch.object(wb, "CONFIG", self.directory / "workbench.toml"),
            patch.object(
                wb, "console", Console(markup=False, highlight=False, width=250)
            ),
        ]:
            patcher.start()
            self.addCleanup(patcher.stop)
        wb._check_version.cache_clear()

    def tearDown(self):
        deactivate_all()

    def request(self, method, url, *, headers, timeout, params=None, json=None):
        url = urllib.parse.urlsplit(url)
        path = url.path
        if params and method != "GET":
            path = f"{path}?{urllib.parse.urlencode(params, doseq=True)}"
        if method == "GET":
            response = self.api_client.get(path, params, headers=headers)
        else:
            response = getattr(self.api_client, method.lower())(
                path, json, content_type="application/json", headers=headers
            )
        return Response(response)

    def wb(self, *args, user=None, token=None):
        if not token:
            _token, token = APIToken.create_for(user=user or self.user, title="Tests")
        result = CliRunner().invoke(
            wb.cli,
            [str(arg) for arg in args],
            env={"WORKBENCH_URL": "http://testserver", "WORKBENCH_TOKEN": token},
        )
        if result.exception and not isinstance(result.exception, SystemExit):
            raise result.exception
        return result

    def file(self, content):
        path = self.directory / "data.yaml"
        path.write_text(content)
        return path

    @property
    def user(self):
        if not hasattr(self, "_user"):
            self._user = factories.UserFactory.create(_short_name="ab")
        return self._user

    def test_projects(self):
        """Search, show and create projects"""
        project = factories.ProjectFactory.create(title="Relaunch", owned_by=self.user)
        factories.OfferFactory.create(project=project, title="Phase 1")

        result = self.wb("whoami")
        self.assertEqual(result.exit_code, 0)
        self.assertIn(self.user.get_full_name(), result.output)

        result = self.wb("projects", "search", "relaunch")
        self.assertIn(project.code, result.output)
        result = self.wb("projects", "show", project.pk)
        self.assertIn("Phase 1", result.output)

        result = self.wb("contacts", "search", project.customer.name.split()[0])
        self.assertIn(project.customer.name, result.output)

        result = self.wb(
            "projects",
            "create",
            "--title",
            "Second",
            "--contact",
            project.contact_id,
            "--dry-run",
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Dry run", result.output)

        # Warnings of the web interface are errors without a field
        result = self.wb(
            "projects", "create", "--title", "Second", "--customer", project.customer_id
        )
        self.assertEqual(result.exit_code, 1)
        self.assertIn("No contact selected.\n", result.output)

    def test_offers(self):
        """Offers are created and replaced from YAML files"""
        factories.service_types()
        project = factories.ProjectFactory.create(owned_by=self.user)
        offer = self.file(
            """\
title: Relaunch
postal_address: "A\\nB\\nC"
services:
  - title: Concept
    service_type: consulting
    hours: 10
  - title: Hosting
    cost: 500
"""
        )

        result = self.wb("offers", "create", project.pk, offer, "--dry-run")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("3000.00", result.output)
        self.assertFalse(Offer.objects.exists())

        result = self.wb("offers", "create", project.pk, offer)
        created = Offer.objects.get()
        self.assertIn(created.code, result.output)

        result = self.wb("offers", "list", project.pk)
        self.assertIn(created.code, result.output)

        self.file("title: Smaller\nservices:\n  - title: Concept\n    hours: 1\n")
        result = self.wb("offers", "replace", created.pk, offer)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("services.0.hours: ", result.output)

    def test_planning(self):
        """Dates in YAML files are sent as strings"""
        factories.service_types()
        project = factories.ProjectFactory.create(owned_by=self.user)
        plan = self.file(
            f"""\
milestones:
  - key: launch
    title: Launch
    date: {in_days(60).isoformat()}
planned_work:
  - title: Concept
    user: AB
    service_type: consulting
    milestone: launch
    weeks: [{monday().isoformat()}]
    planned_hours: 8
"""
        )
        result = self.wb("planning", "import", project.pk, plan, "--dry-run")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Launch", result.output)
        self.assertIn("Dry run", result.output)

    def test_reporting(self):
        """Statistics, invoices, deals, overview and key figures"""
        project = factories.ProjectFactory.create(owned_by=self.user)
        factories.InvoiceFactory.create(
            project=project, customer=project.customer, title="Kick-off"
        )
        factories.DealFactory.create(owned_by=self.user, title="Big deal")

        result = self.wb("projects", "stats", project.pk, "--csv")
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.output.startswith("project_id,project,"))

        self.assertIn("Kick-off", self.wb("invoices", "list").output)
        self.assertIn("Kick-off", self.wb("projects", "invoicing", project.pk).output)
        self.assertIn("Big deal", self.wb("deals", "list").output)

        result = self.wb("me")
        self.assertIn(project.code, result.output)
        self.assertIn("Big deal", result.output)

        result = self.wb("reports", "cash-data", "--date", dt.date.today())
        self.assertEqual(result.exit_code, 0)
        self.assertIn('"open_invoices"', result.output)

    @override_settings(FEATURES={FEATURES.CONTROLLING: F.NEVER})
    def test_missing_feature(self):
        """Projects are shown without offers, offers aren't"""
        project = factories.ProjectFactory.create(title="Relaunch")
        factories.OfferFactory.create(project=project, title="Phase 1")

        result = self.wb("projects", "show", project.pk)
        self.assertEqual(result.exit_code, 0)
        self.assertNotIn("Phase 1", result.output)

        result = self.wb("offers", "list", project.pk)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("403", result.output)

    def test_unauthorized(self):
        """Invalid tokens tell people to log in again"""
        result = self.wb("whoami", token="wb_nope")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("wb login", result.output)

    def test_versions(self):
        """Outdated CLIs are told to upgrade, too old ones are rejected"""
        with patch.object(cli_version, "LATEST", "99.0.0"):
            result = self.wb("whoami")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("wb 99.0.0 is available", result.output)

        with patch.object(cli_version, "MINIMUM", (99, 0, 0)):
            result = self.wb("whoami")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("uv tool upgrade workbench-cli", result.output)

    def test_browser_login(self):
        """wb login authorizes the CLI in the browser"""
        browser = Client()
        browser.force_login(self.user)

        def open_browser(url):
            # The browser authorizes wb and posts the token to the local port.
            # Only the last step happens in a thread: The others need the
            # database connection of the test.
            url = urllib.parse.urlsplit(url)
            page = browser.post(f"{url.path}?{url.query}").content.decode()
            action = re.search(r'action="(http://127[^"]+)"', page).group(1)
            fields = dict(re.findall(r'name="(token|state)" value="([^"]+)"', page))
            threading.Thread(
                target=urllib.request.urlopen,
                args=[action, urllib.parse.urlencode(fields).encode()],
            ).start()

        class Thread:
            def __init__(self, *, target, args, daemon):
                self.target, self.args = target, args

            def start(self):
                self.target(*self.args)

        with (
            patch.object(wb.webbrowser, "open", open_browser),
            patch.object(wb, "threading", types.SimpleNamespace(Thread=Thread)),
        ):
            result = CliRunner().invoke(wb.cli, ["login", "http://testserver"])
        self.assertEqual(result.exit_code, 0, result.output)

        config = wb.CONFIG.read_text()
        self.assertIn('url = "http://testserver"', config)
        token = re.search(r'token = "([^"]+)"', config).group(1)
        self.assertEqual(APIToken.objects.user_for(token), self.user)
