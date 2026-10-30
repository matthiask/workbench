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
from click.shell_completion import get_completion_class
from click.testing import CliRunner
from django.test import Client, TestCase
from django.test.utils import override_settings
from django.utils.translation import deactivate_all
from rich.console import Console

from workbench import cli_version, factories
from workbench.accounts.features import FEATURES, F
from workbench.accounts.models import APIToken
from workbench.contacts.models import Person
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
            patch.object(wb, "BUG_REPORTS", self.directory / "reports"),
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

    def wb(self, *args, user=None, token=None, debug=True):
        if not token:
            _token, token = APIToken.create_for(user=user or self.user, title="Tests")
        result = CliRunner().invoke(
            wb.cli,
            [str(arg) for arg in args],
            env={
                "WORKBENCH_URL": "http://testserver",
                "WORKBENCH_TOKEN": token,
                "WB_DEBUG": "1" if debug else "",
            },
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

        deal = factories.DealFactory.create(title="Noted deal")
        result = self.wb(
            "notes",
            "create",
            "--deal",
            deal.pk,
            "--title",
            "Call",
            "--description",
            "Budget approved",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        result = self.wb("notes", "search", "budget")
        self.assertIn("Noted deal", result.output)
        self.assertIn("Budget approved", result.output)
        result = self.wb("notes", "create", "--title", "Call", "--description", "x")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("exactly one of deal, invoice, recurring_invoice", result.output)

        result = self.wb("me")
        self.assertEqual(result.exit_code, 0)
        self.assertIn(self.user.get_full_name(), result.output)

        result = self.wb("users", "search", self.user._short_name)
        self.assertEqual(result.exit_code, 0)
        self.assertIn(self.user.get_full_name(), result.output)

        result = self.wb("projects", "search", "relaunch")
        self.assertIn(project.code, result.output)
        result = self.wb("projects", "show", project.pk)
        self.assertIn("Phase 1", result.output)

        result = self.wb("contacts", "search", project.customer.name.split()[0])
        self.assertIn(project.customer.name, result.output)
        result = self.wb("organizations", "show", project.customer_id)
        self.assertIn(project.contact.full_name, result.output)
        result = self.wb("people", "show", project.contact_id)
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

    def test_people(self):
        """People are created from YAML files"""
        person = self.file(
            """\
given_name: Hans
family_name: Muster
salutation: Lieber Hans
new_organization: Beispiel AG
email_addresses:
  - email: hans@example.com
"""
        )
        result = self.wb("people", "create", person, "--dry-run")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("hans@example.com", result.output)
        self.assertIn("Dry run", result.output)

        result = self.wb("people", "create", person)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Beispiel AG", result.output)

        result = self.wb("people", "create", person, "--allow-duplicates")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("email_addresses.0.email: ", result.output)

        created = Person.objects.get()
        details = self.file("phone_numbers:\n  - phone_number: 044 123 45 67\n")
        result = self.wb("people", "add-details", created.pk, details)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("+41441234567", result.output)

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

        result = self.wb("offers", "search", "--project", project.pk)
        self.assertIn(created.code, result.output)

        result = self.wb("offers", "search", "relaunch", "--status", "in_preparation")
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
        factories.ProjectedInvoiceFactory.create(
            project=project, description="Planning"
        )
        factories.DealFactory.create(owned_by=self.user, title="Big deal")

        factories.LoggedHoursFactory.create(
            service=factories.ServiceFactory.create(project=project),
            rendered_by=self.user,
            hours=3,
            description="Wireframes",
        )
        result = self.wb("services", "search", "--project", project.pk)
        self.assertIn("3.0", result.output)
        result = self.wb(
            "hours", "search", "--project", project.pk, "--rendered-by", "ab"
        )
        self.assertIn("Wireframes", result.output)
        self.assertIn("3.0", result.output)

        factories.AbsenceFactory.create(
            user=self.user, starts_on=in_days(7), description="Holidays"
        )
        factories.AbsenceFactory.create(starts_on=in_days(-7), description="Past")
        result = self.wb("absences", "search")
        self.assertIn("Holidays", result.output)
        self.assertNotIn("Past", result.output)

        factories.LoggedCostFactory.create(
            service=factories.ServiceFactory.create(project=project),
            cost=120,
            description="Fonts",
        )
        result = self.wb("costs", "search", "--project", project.pk)
        self.assertIn("Fonts", result.output)
        self.assertIn("120.00", result.output)

        result = self.wb("projects", "stats", project.pk, "--csv")
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.output.startswith("project_id,project,"))

        self.assertIn("Kick-off", self.wb("invoices", "search", "kick").output)
        self.assertIn(
            "Kick-off", self.wb("invoices", "search", "--project", project.pk).output
        )
        result = self.wb("projected-invoices", "search", "--project", project.pk)
        self.assertIn("Planning", result.output)
        self.assertIn("Big deal", self.wb("deals", "search").output)

        factories.ValueTypeFactory.create(title="Design")
        result = self.wb(
            "deals",
            "create",
            "--title",
            "Bigger deal",
            "--contact",
            project.contact_id,
            "--probability",
            "normal",
            "--value",
            "design=5000",
            "--dry-run",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("5000.00", result.output)
        self.assertIn("Dry run", result.output)
        result = self.wb(
            "deals", "create", "--title", "X", "--probability", "low", "--value", "nope"
        )
        self.assertEqual(result.exit_code, 1)
        self.assertIn("--value expects KEY=VALUE", result.output)

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

        result = self.wb("offers", "search")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("403", result.output)

    def test_unauthorized(self):
        """Invalid tokens tell people to log in again"""
        result = self.wb("me", token="wb_nope")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("wb login", result.output)

    def test_bug_reports(self):
        """Crashes and server errors write a bug report people can send"""
        person = factories.PersonFactory.create()
        with patch.object(wb, "_echo_person", side_effect=KeyError("url")):
            result = self.wb("people", "show", person.pk, debug=False)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("wb crashed (KeyError: 'url')", result.output)
        [report] = (self.directory / "reports").iterdir()
        self.assertIn(str(report), result.output)
        content = report.read_text()
        self.assertIn(f"wb {wb.VERSION}", content)
        self.assertIn("Installation: http://testserver", content)
        self.assertIn(f"Command: wb people show {person.pk}", content)
        self.assertIn("Traceback", content)
        report.unlink()

        with (
            patch.object(wb, "_echo_person", side_effect=KeyError("url")),
            self.assertRaises(KeyError),
        ):
            self.wb("people", "show", person.pk)

        with patch.object(
            self.api_client,
            "get",
            return_value=types.SimpleNamespace(
                status_code=500, headers={}, content=b"Server Error (500)"
            ),
        ):
            result = self.wb("people", "show", person.pk, debug=False)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Workbench failed (500).", result.output)
        [report] = (self.directory / "reports").iterdir()
        self.assertIn(f"GET contacts/people/{person.pk}/", report.read_text())
        self.assertIn("Server Error (500)", report.read_text())

    def test_versions(self):
        """Outdated CLIs are told to upgrade, too old ones are rejected"""
        with patch.object(cli_version, "LATEST", "99.0.0"):
            result = self.wb("me")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("wb 99.0.0 is available", result.output)

        with patch.object(cli_version, "MINIMUM", (99, 0, 0)):
            result = self.wb("me")
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
        self.assertIn('current = "http://testserver"', config)
        token = re.search(r'token = "([^"]+)"', config).group(1)
        self.assertEqual(APIToken.objects.user_for(token), self.user)

    def test_auth_urls(self):
        """Installations are identified by the scheme and the host only"""
        _token, old = APIToken.create_for(user=self.user, title="Old")
        _token, new = APIToken.create_for(user=self.user, title="New")
        # Older versions stored the URL as given
        wb.CONFIG.write_text(f'url = "http://testserver/"\ntoken = "{old}"\n')

        result = CliRunner().invoke(
            wb.cli, ["login", "http://testserver", "--token"], input=new, env={}
        )
        self.assertEqual(result.exit_code, 0, result.output)
        result = CliRunner().invoke(wb.cli, ["auth", "list"], env={})
        self.assertEqual(result.output, "* http://testserver\n")

        # Pasted from the browser, or without the scheme
        for url in ["http://TestServer/accounts/login/?next=/", "other.example.com"]:
            result = CliRunner().invoke(
                wb.cli, ["login", url, "--token"], input=new, env={}
            )
            self.assertEqual(result.exit_code, 0, result.output)
        result = CliRunner().invoke(wb.cli, ["auth", "list"], env={})
        self.assertEqual(
            result.output, "  http://testserver\n* https://other.example.com\n"
        )

    def test_completion(self):
        """Shells complete commands and the installations to switch to"""
        result = CliRunner().invoke(wb.cli, ["completion", "bash"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("_WB_COMPLETE=bash_complete", result.output)

        wb.CONFIG.write_text(
            'current = "https://a.example.com"\n'
            '[installations."https://a.example.com"]\ntoken = "a"\n'
            '[installations."https://b.example.org"]\ntoken = "b"\n'
        )

        def complete(args, incomplete):
            complete = get_completion_class("bash")(wb.cli, {}, "wb", "_WB_COMPLETE")
            return [item.value for item in complete.get_completions(args, incomplete)]

        self.assertIn("switch", complete(["auth"], ""))
        # Host names only: bash splits words at the colon of https://
        self.assertEqual(
            complete(["auth", "switch"], ""), ["a.example.com", "b.example.org"]
        )
        self.assertEqual(complete(["auth", "switch"], "org"), ["b.example.org"])
        # Options are offered when there's nothing else to complete
        self.assertIn("--status", complete(["deals", "search"], ""))
        self.assertIn("--status", complete(["deals", "search", "relaunch"], ""))
        # but not where a value is expected
        self.assertEqual(complete(["deals", "search", "--customer"], ""), [])
        self.assertEqual(complete(["deals", "search", "--status"], "o"), ["open"])

    def test_auth(self):
        """wb is logged in to several installations and switches between them"""
        _token, first = APIToken.create_for(user=self.user, title="First")
        other = factories.UserFactory.create()
        _token, second = APIToken.create_for(user=other, title="Second")
        # The configuration of older versions
        wb.CONFIG.write_text(f'url = "http://first.example.com"\ntoken = "{first}"\n')

        def run(*args, env=None, input=None):
            return CliRunner().invoke(wb.cli, args, env=env or {}, input=input)

        result = run("login", "http://second.example.com/", "--token", input=second)
        self.assertEqual(result.exit_code, 0, result.output)
        result = run("auth", "list")
        self.assertEqual(
            result.output,
            "  http://first.example.com\n* http://second.example.com\n",
        )
        self.assertIn(other.get_full_name(), run("me").output)

        result = run("auth", "switch", "example")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Several installations match", result.output)
        self.assertEqual(
            run("auth", "switch", "first").output, "Using http://first.example.com\n"
        )
        self.assertIn(self.user.get_full_name(), run("me").output)

        # WORKBENCH_URL selects another installation for one command
        result = run("me", env={"WORKBENCH_URL": "http://second.example.com"})
        self.assertIn(other.get_full_name(), result.output)
        self.assertIn("* http://first.example.com", run("auth", "list").output)
