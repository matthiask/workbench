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

from workbench import cli_version, factories
from workbench.accounts.features import FEATURES, F
from workbench.accounts.models import APIToken
from workbench.contacts.models import Person
from workbench.deals.models import Deal
from workbench.invoices.models import Invoice
from workbench.offers.models import Offer
from workbench.timer.models import Timestamp
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
            patch.object(wb.core.requests, "request", self.request),
            patch.object(wb.core, "CONFIG", self.directory / "workbench.toml"),
            patch.object(wb.core, "BUG_REPORTS", self.directory / "reports"),
            patch.object(wb.core, "CACHE", self.directory / "cache"),
            patch.object(wb.core.console, "_width", 250),
        ]:
            patcher.start()
            self.addCleanup(patcher.stop)
        wb.core._check_version.cache_clear()

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
            _token, token = APIToken.create_for(
                user=user or self.user, title="Tests", access="write"
            )
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

        result = self.wb("projects", "update", project.pk, "--title", "Relaunch 2027")
        self.assertEqual(result.exit_code, 0, result.output)
        result = self.wb("projects", "update", project.pk, "--close")
        self.assertIn(f"Closed on  {dt.date.today()}", result.output)
        project.refresh_from_db()
        self.assertEqual(
            (project.title, project.closed_on), ("Relaunch 2027", dt.date.today())
        )
        self.wb("projects", "update", project.pk, "--reopen")
        project.refresh_from_db()
        self.assertIsNone(project.closed_on)
        result = self.wb("projects", "update", project.pk, "--close", "--reopen")
        self.assertEqual(result.exit_code, 1)

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

        # Single services
        concept, hosting = created.services.all()
        result = self.wb("offers", "update", created.pk, "--title", "Website")
        self.assertIn("Website", result.output)
        self.assertIn(str(concept.pk), result.output)

        result = self.wb(
            "offers",
            "services",
            "add",
            created.pk,
            "--title",
            "Design",
            "--service-type",
            "production",
            "--hours",
            5,
            "--after",
            concept.pk,
            "--dry-run",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("(new)", result.output)
        self.assertIn("3900.00", result.output)
        self.assertIn("Dry run", result.output)
        self.assertEqual(created.services.count(), 2)

        self.file("title: Design\nservice_type: production\nhours: 5\n")
        result = self.wb("offers", "services", "add", created.pk, offer, "--hours", 6)
        self.assertEqual(result.exit_code, 0, result.output)
        design = created.services.get(title="Design")
        self.assertEqual(design.effort_hours, 6)

        result = self.wb(
            "offers", "services", "update", created.pk, hosting.pk, "--clear-cost"
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Warning: Hosting: Neither hours nor a cost", result.output)
        result = self.wb(
            "offers",
            "services",
            "update",
            created.pk,
            hosting.pk,
            "--cost",
            600,
            "--optional",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        hosting.refresh_from_db()
        self.assertEqual((hosting.cost, hosting.is_optional), (600, True))

        result = self.wb(
            "offers",
            "services",
            "reorder",
            created.pk,
            hosting.pk,
            design.pk,
            concept.pk,
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            [s.pk for s in created.services.all()], [hosting.pk, design.pk, concept.pk]
        )
        result = self.wb("offers", "services", "delete", created.pk, design.pk)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(created.services.count(), 2)

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

    def test_logbook(self):
        """Services, logged hours and costs, absences and project statistics"""
        project = factories.ProjectFactory.create(owned_by=self.user)
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
        result = self.wb("hours", "search", "--period", "this-month")
        self.assertIn("Wireframes", result.output)
        result = self.wb("hours", "search", "--csv")
        self.assertTrue(result.output.startswith("id,url,rendered_on,"), result.output)
        self.assertIn("project.code", result.output.splitlines()[0])
        self.assertIn("Wireframes", result.output)
        result = self.wb("hours", "search", "--period", "last-year")
        self.assertNotIn("Wireframes", result.output)

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

    def test_absences(self):
        factories.AbsenceFactory.create(
            user=self.user, starts_on=in_days(7), description="Holidays"
        )
        factories.AbsenceFactory.create(starts_on=in_days(-7), description="Past")
        result = self.wb(
            "absences",
            "create",
            "--starts-on",
            in_days(14),
            "--days",
            2,
            "--reason",
            "vacation",
            "--description",
            "Skiing",
            "--dry-run",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Skiing", result.output)
        self.assertIn("Dry run", result.output)

        result = self.wb("absences", "search")
        self.assertIn("Holidays", result.output)
        self.assertNotIn("Past", result.output)

    def test_invoices(self):
        """Invoices, projected and recurring invoices, and pagination"""
        project = factories.ProjectFactory.create(owned_by=self.user)
        factories.InvoiceFactory.create(
            project=project, customer=project.customer, title="Kick-off"
        )
        factories.InvoiceFactory.create(
            project=project, customer=project.customer, title="Follow-up"
        )
        factories.ProjectedInvoiceFactory.create(
            project=project, description="Planning"
        )
        factories.RecurringInvoiceFactory.create(title="Hosting 2027")

        result = self.wb("invoices", "search", "--project", project.pk, "--limit", 1)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(
            "Showing 1–1 of 2 invoices, use --offset 1 for more.", result.output
        )
        result = self.wb(
            "invoices", "search", "--project", project.pk, "--offset", 1, "--json"
        )
        self.assertIn('"count": 2', result.output)
        self.assertNotIn("Showing", result.output)

        self.assertIn("Kick-off", self.wb("invoices", "search", "kick").output)
        self.assertIn(
            "Kick-off", self.wb("invoices", "search", "--project", project.pk).output
        )
        result = self.wb("projected-invoices", "search", "--project", project.pk)
        self.assertIn("Planning", result.output)
        result = self.wb("recurring-invoices", "search", "hosting")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Hosting 2027", result.output)

    def test_invoice_reminders(self):
        project = factories.ProjectFactory.create(owned_by=self.user)
        overdue = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            title="Kick-off",
            status=Invoice.SENT,
            invoiced_on=in_days(-70),
            due_on=in_days(-40),
        )
        result = self.wb("invoices", "reminders")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Kick-off", result.output)
        self.assertIn("40 days", result.output)
        result = self.wb("invoices", "mark-reminded", overdue.pk)
        self.assertEqual(result.exit_code, 0, result.output)
        overdue.refresh_from_db()
        self.assertEqual(overdue.last_reminded_on, dt.date.today())
        result = self.wb("invoices", "postpone-reminders", overdue.pk, in_days(40))
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Are you sure?", result.output)
        result = self.wb(
            "invoices", "postpone-reminders", overdue.pk, in_days(40), "--confirm"
        )
        self.assertIn("postponed until", result.output)
        result = self.wb("invoices", "postpone-reminders", overdue.pk, "--clear")
        self.assertIn("aren't postponed anymore", result.output)

    def test_deals(self):
        """Searching, creating, updating, closing and reopening deals"""
        project = factories.ProjectFactory.create(owned_by=self.user)
        factories.DealFactory.create(owned_by=self.user, title="Big deal")
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

        open_deal = factories.DealFactory.create(
            title="Website", owned_by=self.user, probability=Deal.NORMAL
        )
        result = self.wb(
            "deals", "update", open_deal.pk, "--title", "Website 2027", "--dry-run"
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Website 2027", result.output)
        self.assertIn("Dry run", result.output)
        factories.ClosingTypeFactory.create(title="Won", represents_a_win=True)
        result = self.wb(
            "deals", "close", open_deal.pk, "accepted", "--closing-type", "x"
        )
        self.assertEqual(result.exit_code, 1)
        self.assertIn("'Won'", result.output)
        result = self.wb(
            "deals", "close", open_deal.pk, "accepted", "--closing-type", "won"
        )
        self.assertEqual(result.exit_code, 0, result.output)
        open_deal.refresh_from_db()
        self.assertEqual(open_deal.status, Deal.ACCEPTED)
        result = self.wb("deals", "reopen", open_deal.pk)
        open_deal.refresh_from_db()
        self.assertEqual(open_deal.status, Deal.OPEN)

    def test_deal_stats(self):
        deal = factories.DealFactory.create(
            title="Relaunch",
            owned_by=self.user,
            status=Deal.DECLINED,
            closed_on=dt.date.today(),
        )
        result = self.wb("deals", "stats", "--user", "ab")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Relaunch", result.output)
        result = self.wb("deals", "history")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(deal.code, result.output)

    def test_me_and_teams(self):
        project = factories.ProjectFactory.create(owned_by=self.user)
        factories.DealFactory.create(owned_by=self.user, title="Big deal")
        result = self.wb("me")
        self.assertIn(project.code, result.output)
        self.assertIn("Big deal", result.output)

        factories.TeamFactory.create(name="Design").members.add(self.user)
        result = self.wb("teams", "search")
        self.assertIn("Design", result.output)
        self.assertIn("ab", result.output)

    def test_defaults(self):
        """Nouns without a command show what's most often wanted"""
        project = factories.ProjectFactory.create(owned_by=self.user, title="Mine")
        factories.ProjectFactory.create(title="Someone else's")
        factories.LoggedHoursFactory.create(
            service=factories.ServiceFactory.create(project=project),
            rendered_by=self.user,
            description="Wireframes",
        )
        factories.DealFactory.create(owned_by=self.user, title="Big deal")
        factories.AbsenceFactory.create(
            user=self.user, starts_on=in_days(7), description="Holidays"
        )
        factories.TeamFactory.create(name="Design").members.add(self.user)

        result = self.wb("projects")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Mine", result.output)
        self.assertNotIn("Someone else's", result.output)
        self.assertIn("Wireframes", self.wb("hours").output)
        self.assertIn("Big deal", self.wb("deals").output)
        self.assertIn("No offers which may need action", self.wb("offers").output)
        self.assertIn("Holidays", self.wb("absences").output)
        self.assertIn("ab", self.wb("planning").output)
        self.assertIn(self.user.get_full_name(), self.wb("users").output)
        self.assertIn("Design", self.wb("teams").output)
        for noun in ["invoices", "recurring-invoices", "projected-invoices"]:
            self.assertEqual(self.wb(noun).exit_code, 0)

    @override_settings(FEATURES={FEATURES.CONTROLLING: F.NEVER})
    def test_defaults_missing_feature(self):
        result = self.wb("offers")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Requires the controlling feature", result.output)

    def test_search(self):
        """wb search finds everything like the web interface's search field"""
        project = factories.ProjectFactory.create(title="Relaunch website")
        factories.OfferFactory.create(project=project, title="Relaunch phase 1")
        factories.ProjectFactory.create(title="Relaunch shop")
        factories.PersonFactory.create(given_name="Ronja", family_name="Relaunch")

        result = self.wb("search", "relaunch")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Relaunch website", result.output)
        self.assertIn("Relaunch phase 1", result.output)
        self.assertIn("Ronja", result.output)
        self.assertIn("(people)", result.output)

        self.assertIn(
            "Projects (projects), 1 of 2",
            self.wb("search", "relaunch", "--limit", 1).output,
        )
        result = self.wb("search", "relaunch", "--limit", 1, "--json")
        self.assertIn('"count": 2', result.output)

        self.assertIn("No results found.", self.wb("search", "nothing").output)
        self.assertEqual(self.wb("search").exit_code, 2)

    def test_planning_export(self):
        project = factories.ProjectFactory.create(owned_by=self.user)
        factories.PlannedWorkFactory.create(
            project=project,
            user=self.user,
            title="Wireframes",
            weeks=[monday()],
            planned_hours=8,
        )
        result = self.wb("planning", "export", "--user", "ab")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Wireframes", result.output)
        self.assertIn("ab free", result.output)
        result = self.wb("planning", "export", "--project", project.pk, "--csv")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(result.output.startswith("week,project_id,"))
        self.assertIn(f"{monday().isoformat()},{project.pk},", result.output)

    def test_reports(self):
        """Reports as tables, as JSON and as CSV"""
        project = factories.ProjectFactory.create(owned_by=self.user)
        service = factories.ServiceFactory.create(project=project, effort_rate=100)
        factories.LoggedHoursFactory.create(
            service=service, rendered_by=self.user, hours=3
        )
        factories.LoggedCostFactory.create(
            service=service, cost=150, third_party_costs=120
        )
        factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            title="Kick-off",
            status=Invoice.SENT,
            invoiced_on=in_days(-70),
            due_on=in_days(-40),
            subtotal=200,
        )
        factories.ProjectedInvoiceFactory.create(
            project=project, invoiced_on=in_days(30), gross_margin=1000
        )

        for args, expected in [
            (["projected-gross-margin"], "920.00"),
            (["budget", "--owned-by", "ab"], project.code),
            (["third-party-costs"], "120.00"),
            (["open-items"], "Kick-off"),
            (["hours-per-customer", "--user", "ab"], project.customer.name),
            (["hours-per-type"], "ab"),
            (["green-hours", "--period", f"{dt.date.today():%Y-%m}"], "3.0"),
            (["planning-vs-logbook"], project.customer.name),
            (["logging"], "ab"),
            (["squeeze", "--since", in_days(-7), "--until", dt.date.today()], "ab"),
        ]:
            with self.subTest(args=args):
                result = self.wb("reports", *args)
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertIn(expected, result.output)
                result = self.wb("reports", *args, "--json")
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertTrue(result.output.startswith("{"))
                result = self.wb("reports", *args, "--csv")
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(len(result.output.splitlines()), 2, result.output)

        result = self.wb("reports", "hours-per-type", "--period", "nope")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("period", result.output)

    def test_key_data_and_cash_data(self):
        project = factories.ProjectFactory.create(owned_by=self.user)
        factories.InvoiceFactory.create(project=project, customer=project.customer)
        result = self.wb("reports", "key-data", "--month", "2026-01")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Key data 2026-01", result.output)
        self.assertIn("Deals funnel", result.output)
        result = self.wb("reports", "key-data", "--month", "2026-01", "--json")
        self.assertIn('"month": "2026-01"', result.output)

        result = self.wb("reports", "cash-data", "--date", dt.date.today())
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Open invoices excl. tax", result.output)
        self.assertIn("Planned invoicing", result.output)
        result = self.wb("reports", "cash-data", "--json")
        self.assertIn('"open_invoices"', result.output)

    def test_working_time(self):
        factories.YearFactory.create(working_time_model=self.user.working_time_model)
        factories.EmploymentFactory.create(
            user=self.user, date_from=dt.date.today().replace(month=1, day=1)
        )
        result = self.wb("reports", "working-time")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Balance incl. vacation days left", result.output)
        result = self.wb("reports", "working-time", "--weekly")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(monday().isoformat(), result.output)

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

    def test_timestamps(self):
        """Tasks are started and stopped like with the old tst command"""
        result = self.wb("timestamps", "start")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("T1: start at", result.output)
        result = self.wb("timestamps", "stop", "-5", "Wireframes", "review")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(", Wireframes review", result.output)
        timestamp = Timestamp.objects.filter(user=self.user).first()
        self.assertEqual(timestamp.notes, "Wireframes review")
        self.assertEqual(timestamp.type, Timestamp.STOP)

        result = self.wb("timestamps", "list")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Wireframes review", result.output)
        self.assertIn("Log hours", result.output)
        self.assertIn("Logged this week: 0.0h", result.output)
        self.assertIn("Running since", result.output)

        result = self.wb("timestamps", "undo")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Deleted T2: start at", result.output)
        # The renumbered list
        self.assertIn("Wireframes review", result.output)
        result = self.wb("timestamps", "delete", "t1")
        self.assertIn("Deleted T1: stop at", result.output)
        self.assertFalse(Timestamp.objects.exists())
        result = self.wb("timestamps", "undo")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("There are no timestamps today", result.output)

    def test_timestamps_alias(self):
        """wb ts is an alias for wb timestamps, which lists today's
        timestamps without a command"""
        result = self.wb("ts", "start", "Wireframes")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("T1: start at", result.output)
        result = self.wb("ts")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Wireframes", result.output)
        self.assertIn("Running since", result.output)
        result = self.wb("timestamps")
        self.assertIn("Wireframes", result.output)

        result = self.wb("--help")
        self.assertIn("Aliases:\n  ts  timestamps", result.output)

        project = factories.ProjectFactory.create()
        result = self.wb("ts", "stop", "-p", str(project.pk), "+5", "Review")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("T2: stop at", result.output)
        self.assertIn(project.code, result.output)
        timestamp = Timestamp.objects.filter(user=self.user).first()
        self.assertEqual(timestamp.project, project)
        self.assertEqual(timestamp.notes, "Review")

    def test_bug_reports(self):
        """Crashes and server errors write a bug report people can send"""
        person = factories.PersonFactory.create()
        with patch.object(wb.contacts, "_echo_person", side_effect=KeyError("url")):
            result = self.wb("people", "show", person.pk, debug=False)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("wb crashed (KeyError: 'url')", result.output)
        [report] = (self.directory / "reports").iterdir()
        self.assertIn(str(report), result.output)
        content = report.read_text()
        self.assertIn(f"wb {wb.core.VERSION}", content)
        self.assertIn("Installation: http://testserver", content)
        self.assertIn(f"Command: wb people show {person.pk}", content)
        self.assertIn("Traceback", content)
        report.unlink()

        with (
            patch.object(wb.contacts, "_echo_person", side_effect=KeyError("url")),
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
            patch.object(wb.core.webbrowser, "open", open_browser),
            patch.object(wb.core, "threading", types.SimpleNamespace(Thread=Thread)),
        ):
            result = CliRunner().invoke(wb.cli, ["login", "http://testserver"])
            self.assertEqual(result.exit_code, 1)
            self.assertIn("--read", result.output)
            result = CliRunner().invoke(
                wb.cli, ["login", "http://testserver", "--read"]
            )
        self.assertEqual(result.exit_code, 0, result.output)

        config = wb.core.CONFIG.read_text()
        self.assertIn('current = "http://testserver"', config)
        # Expired tokens are replaced with the same access
        self.assertIn('access = "read"', config)
        token = re.search(r'token = "([^"]+)"', config).group(1)
        self.assertEqual(APIToken.objects.for_secret(token).user, self.user)

    def test_auth_urls(self):
        """Installations are identified by the scheme and the host only"""
        _token, old = APIToken.create_for(user=self.user, title="Old", access="write")
        _token, new = APIToken.create_for(user=self.user, title="New", access="write")
        # Older versions stored the URL as given
        wb.core.CONFIG.write_text(f'url = "http://testserver/"\ntoken = "{old}"\n')

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

        wb.core.CONFIG.write_text(
            'current = "https://a.example.com"\n'
            '[installations."https://a.example.com"]\ntoken = "a"\n'
            '[installations."https://b.example.org"]\ntoken = "b"\n'
        )

        def complete(args, incomplete):
            complete = get_completion_class("bash")(wb.cli, {}, "wb", "_WB_COMPLETE")
            return [item.value for item in complete.get_completions(args, incomplete)]

        self.assertIn("switch", complete(["auth"], ""))
        self.assertIn("services", complete(["offers"], ""))
        self.assertEqual(
            complete(["offers", "services"], ""), ["add", "delete", "reorder", "update"]
        )
        self.assertIn("--clear-cost", complete(["offers", "services", "update"], "--"))
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

    def test_completion_values(self):
        """Short names and teams are completed from the API, cached for a day"""
        _token, secret = APIToken.create_for(
            user=self.user, title="Tests", access="write"
        )
        factories.UserFactory.create(_short_name="abc")
        factories.TeamFactory.create(name="Design")
        wb.core.CONFIG.write_text(
            'current = "http://testserver"\n'
            f'[installations."http://testserver"]\ntoken = "{secret}"\n'
        )

        def complete(args, incomplete):
            complete = get_completion_class("bash")(wb.cli, {}, "wb", "_WB_COMPLETE")
            return [item.value for item in complete.get_completions(args, incomplete)]

        self.assertEqual(
            complete(["hours", "search", "--rendered-by"], "A"), ["ab", "abc"]
        )
        self.assertEqual(
            complete(["reports", "green-hours", "--team"], "d"), ["Design"]
        )

        # Cached
        factories.UserFactory.create(_short_name="abcd")
        self.assertEqual(
            complete(["deals", "search", "--owned-by"], "ab"), ["ab", "abc"]
        )
        for path in (self.directory / "cache").iterdir():
            path.unlink()
        self.assertIn("abcd", complete(["deals", "search", "--owned-by"], "ab"))

        # Nothing without access
        wb.core.CONFIG.write_text("")
        for path in (self.directory / "cache").iterdir():
            path.unlink()
        self.assertEqual(complete(["deals", "search", "--owned-by"], ""), [])

    def test_auth(self):
        """wb is logged in to several installations and switches between them"""
        _token, first = APIToken.create_for(
            user=self.user, title="First", access="write"
        )
        other = factories.UserFactory.create()
        _token, second = APIToken.create_for(user=other, title="Second", access="write")
        # The configuration of older versions
        wb.core.CONFIG.write_text(
            f'url = "http://first.example.com"\ntoken = "{first}"\n'
        )

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
