import datetime as dt
import json
import os
import re
import tempfile
import threading
import types
import urllib.parse
import urllib.request
from pathlib import Path
from unittest.mock import patch

import click
import wb
from click.shell_completion import get_completion_class
from click.testing import CliRunner
from django.test import Client, TestCase
from django.test.utils import override_settings
from django.utils.translation import deactivate_all

from workbench import cli_version, factories
from workbench.accounts.features import FEATURES, F
from workbench.accounts.models import APIToken
from workbench.api_keys import KEYS
from workbench.contacts.models import Group, Organization, Person
from workbench.deals.models import AttributeGroup, Deal
from workbench.invoices.models import Invoice
from workbench.offers.models import Offer
from workbench.projects.models import InternalType, Project, Service
from workbench.timer.models import Timestamp
from workbench.tools.validation import in_days, monday


class Response:
    """The parts of a requests response the CLI uses"""

    def __init__(self, response):
        self.status_code = response.status_code
        self.ok = response.status_code < 400
        self.headers = response.headers
        self.content = response.content
        self.text = response.content.decode(errors="replace")
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

    def wb(self, *args, user=None, token=None, debug=True, input=None):
        if not token:
            _token, token = APIToken.create_for(
                user=user or self.user, title="Tests", access="write"
            )
        # Store the token like `wb login`, but don't change the current
        # installation, tests may have configured others
        config = wb.core.read_config()
        config["installations"].setdefault("http://testserver", {})["token"] = token
        wb.core.write_config(config)
        result = CliRunner().invoke(
            wb.cli,
            [str(arg) for arg in args],
            env={
                "WORKBENCH_URL": "http://testserver",
                "WB_DEBUG": "1" if debug else "",
            },
            input=input,
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
        self.assertIn(
            "exactly one of deal, invoice, recurring_invoice, project", result.output
        )
        result = self.wb(
            "notes",
            "create",
            "--project",
            project.pk,
            "--title",
            "Debriefing",
            "--description",
            "-",
            input="Prototype first\n\nThen the implementation.\n",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        result = self.wb("notes", "search", "--project", project.pk)
        self.assertIn("Prototype first", result.output)
        self.assertNotIn("Budget approved", result.output)

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
        self.assertIn(
            "No contact selected. (warning, ignore with --ignore-warning no-contact)\n",
            result.output,
        )
        result = self.wb(
            "projects",
            "create",
            "--title",
            "Second",
            "--customer",
            project.customer_id,
            "--ignore-warning",
            "no-contact",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(Project.objects.filter(title="Second").exists())

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

        # Closing discards offers in preparation, their planned work needs a
        # decision
        offer = factories.OfferFactory.create(project=project)
        factories.PlannedWorkFactory.create(
            project=project, offer=offer, weeks=[monday() + dt.timedelta(days=7)]
        )
        result = self.wb("projects", "update", project.pk, "--close")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("delete_planned_work", result.output)
        result = self.wb(
            "projects", "update", project.pk, "--close", "--delete-planned-work"
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertFalse(offer.planned_work.exists())

    @override_settings(FEATURES={FEATURES.INTERNAL_TYPES: F.ALWAYS})
    def test_internal_projects(self):
        """Internal projects get their internal type by name"""
        InternalType.objects.create(name="Administration", percentage=100)
        contact = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )
        result = self.wb(
            "projects",
            "create",
            "--title",
            "Bookkeeping",
            "--contact",
            contact.pk,
            "--type",
            "internal",
            "--internal-type",
            "administration",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Internal type  Administration", result.output)
        project = Project.objects.get(title="Bookkeeping")
        self.assertEqual(project.internal_type.name, "Administration")

        result = self.wb("projects", "internal-types")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Administration", result.output)
        self.assertIn(str(project.internal_type.pk), result.output)

        result = self.wb("projects", "update", project.pk, "--type", "order")
        self.assertEqual(result.exit_code, 0, result.output)
        project.refresh_from_db()
        self.assertIsNone(project.internal_type)

    def test_invoices_create(self):
        """Invoices in preparation are created from offers or with amounts"""
        project = factories.ProjectFactory.create(owned_by=self.user)
        factories.PostalAddressFactory.create(person=project.contact)
        offer = factories.OfferFactory.create(project=project, title="Phase 1")
        factories.ServiceFactory.create(
            project=project, offer=offer, title="Design", cost=1000
        )

        result = self.wb("invoices", "create", "--offer", offer.pk, "--dry-run")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Dry run", result.output)
        self.assertFalse(Invoice.objects.exists())

        result = self.wb("invoices", "create", "--offer", offer.pk)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Design", result.output)
        invoice = Invoice.objects.get()
        self.assertEqual(
            (invoice.status, invoice.total_excl_tax), (Invoice.IN_PREPARATION, 1000)
        )

        result = self.wb(
            "invoices", "create", "--project", project.pk, "--type", "down-payment"
        )
        self.assertEqual(result.exit_code, 1)
        self.assertIn("subtotal", result.output)
        result = self.wb(
            "invoices",
            "create",
            "--project",
            project.pk,
            "--type",
            "down-payment",
            "--subtotal",
            "500",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Down payment", result.output)
        down_payment = Invoice.objects.get(type=Invoice.DOWN_PAYMENT)
        down_payment.status = Invoice.SENT
        down_payment.invoiced_on = in_days(0)
        down_payment.save()
        result = self.wb(
            "invoices",
            "create",
            "--project",
            project.pk,
            "--subtotal",
            "2000",
            "--down-payment",
            down_payment.pk,
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("1500.00", result.output)

    def test_pdfs(self):
        """Invoices and offers are saved as PDF"""
        invoice = factories.InvoiceFactory.create(
            owned_by=self.user, title="Relaunch", postal_address="A\nStreet\nCity"
        )
        offer = factories.OfferFactory.create(owned_by=self.user, title="Phase 1")
        self.addCleanup(os.chdir, Path.cwd())
        os.chdir(self.directory)

        result = self.wb("invoices", "pdf", invoice.pk)
        self.assertEqual(result.exit_code, 0, result.output)
        [path] = self.directory.glob("*.pdf")
        self.assertIn(f"Saved {path.name}", result.output)
        self.assertTrue(path.read_bytes().startswith(b"%PDF"))

        target = self.directory / "offer.pdf"
        result = self.wb("offers", "pdf", offer.pk, "-o", target, "--signature-line")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(target.read_bytes().startswith(b"%PDF"))

        with patch(
            "workbench.tools.pdf.PDFDocument.process_invoice",
            side_effect=ValueError("Broken"),
        ):
            result = self.wb("invoices", "pdf", invoice.pk, "-o", target)
        self.assertEqual(result.exit_code, 1)
        # The user's language
        self.assertEqual(result.output, "Konnte das PDF nicht generieren: Broken\n")

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

        group = Group.objects.create(title="Mailing")
        created.groups.add(group)
        result = self.wb("people", "search", "--group", "Mailing")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Hans Muster", result.output)
        result = self.wb("people", "search", "--without-groups", "--csv")
        self.assertNotIn("Hans Muster", result.output)
        result = self.wb(
            "people", "search", "--projects-or-deals-since", "2020-01-01", "--csv"
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertNotIn("Hans Muster", result.output)

        result = self.wb("groups", "create", "Christmas")
        self.assertEqual(result.exit_code, 0, result.output)
        result = self.wb("groups")
        self.assertIn("Christmas", result.output)
        self.assertIn("Mailing", result.output)
        result = self.wb(
            "people",
            "update",
            created.pk,
            "--add-group",
            "Christmas",
            "--remove-group",
            "Mailing",
            "--primary-contact",
            self.user.get_short_name(),
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual([g.title for g in created.groups.all()], ["Christmas"])
        result = self.wb("people", "update", created.pk, "--archive")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("(archived)", result.output)

        former = factories.UserFactory.create(_short_name="old", is_active=False)
        orphan = factories.PersonFactory.create(primary_contact=former)
        factories.ProjectFactory.create(contact=orphan, owned_by=self.user)
        result = self.wb("people", "reassign-suggestions", "--from", "old")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(orphan.full_name, result.output)
        result = self.wb("people", "reassign", "--from", "old", "--suggested")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("1 people reassigned", result.output)
        orphan.refresh_from_db()
        self.assertEqual(orphan.primary_contact, self.user)

        duplicate = factories.PersonFactory.create(given_name="Duplicate")
        factories.ProjectFactory.create(contact=duplicate)
        result = self.wb("people", "merge", duplicate.pk, "--into", orphan.pk)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(
            f"{duplicate.pk} has been merged into {orphan.pk}.", result.output
        )
        self.assertEqual(orphan.project_set.count(), 2)

        christmas = Group.objects.get(title="Christmas")
        result = self.wb("groups", "update", christmas.pk, "--archive")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("(archived)", result.output)
        result = self.wb("groups", "search", "--include-archived")
        self.assertIn("Christmas", result.output)

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
            "services",
            "create",
            "--offer",
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
        self.assertIn("Dry run", result.output)
        self.assertEqual(created.services.count(), 2)

        self.file("title: Design\nservice_type: production\nhours: 5\n")
        result = self.wb(
            "services",
            "create",
            offer,
            "--offer",
            created.pk,
            "--hours",
            6,
            "--after",
            concept.pk,
        )
        self.assertEqual(result.exit_code, 0, result.output)
        design = created.services.get(title="Design")
        self.assertEqual(design.effort_hours, 6)
        self.assertEqual(
            [s.pk for s in created.services.all()], [concept.pk, design.pk, hosting.pk]
        )

        result = self.wb("services", "update", hosting.pk, "--clear-cost")
        self.assertEqual(result.exit_code, 0, result.output)
        hosting.refresh_from_db()
        self.assertIsNone(hosting.cost)
        result = self.wb("services", "update", hosting.pk, "--cost", 600, "--optional")
        self.assertEqual(result.exit_code, 0, result.output)
        hosting.refresh_from_db()
        self.assertEqual((hosting.cost, hosting.is_optional), (600, True))

        result = self.wb("services", "reorder", hosting.pk, design.pk, concept.pk)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            [s.pk for s in created.services.all()], [hosting.pk, design.pk, concept.pk]
        )
        result = self.wb("services", "reorder", hosting.pk, design.pk)
        self.assertEqual(result.exit_code, 1)
        result = self.wb("services", "delete", design.pk)
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

    def test_planned_work(self):
        """Planned work is added, changed and deleted one by one"""
        factories.service_types()
        project = factories.ProjectFactory.create(owned_by=self.user)
        result = self.wb(
            "planning",
            "work",
            "add",
            project.pk,
            "--title",
            "Concept",
            "--user",
            "ab",
            "--service-type",
            "consulting",
            "--week",
            monday().isoformat(),
            "--hours",
            8,
        )
        self.assertEqual(result.exit_code, 0, result.output)
        pw = project.planned_work.get()
        self.assertTrue(pw.is_provisional)

        result = self.wb("planning", "work", "update", pw.pk, "--definitive")
        self.assertEqual(result.exit_code, 0, result.output)
        pw.refresh_from_db()
        self.assertFalse(pw.is_provisional)
        self.assertEqual(self.wb("planning", "work", "update", pw.pk).exit_code, 1)

        result = self.wb("planning", "work", "delete", pw.pk)
        self.assertIn(f"Deleted planned work: {pw.pk}", result.output)
        self.assertFalse(project.planned_work.exists())

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
        service = project.services.get()
        result = self.wb(
            "services",
            "update",
            service.pk,
            "--external-reference",
            "https://example.com/issues/1",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        service.refresh_from_db()
        self.assertEqual(service.external_reference, "https://example.com/issues/1")
        offer = factories.OfferFactory.create(project=project)
        result = self.wb("services", "update", service.pk, "--offer", offer.pk)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(offer.code, result.output)
        result = self.wb("services", "update", service.pk, "--clear-offer")
        self.assertEqual(result.exit_code, 0, result.output)
        service.refresh_from_db()
        self.assertIsNone(service.offer)
        result = self.wb("services", "update", service.pk, "--description", "Text")
        self.assertEqual(result.exit_code, 0, result.output)
        service.refresh_from_db()
        self.assertEqual(service.description, "Text")
        result = self.wb("services", "update", service.pk, "--title", "#12 Issue")
        self.assertEqual(result.exit_code, 0, result.output)
        service.refresh_from_db()
        self.assertEqual(service.title, "#12 Issue")
        result = self.wb("services", "update", service.pk)
        self.assertEqual(result.exit_code, 1)
        result = self.wb("services", "update", service.pk, "--title", "Allgemein")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("--ignore-warning unspecific-service", result.output)
        result = self.wb(
            "services",
            "update",
            service.pk,
            "--title",
            "Allgemein",
            "--ignore-warning",
            "unspecific-service",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        target = factories.ServiceFactory.create(project=project)
        result = self.wb("services", "reassign-logbook", service.pk, "--to", target.pk)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("1 logged hours", result.output)
        self.assertEqual(target.loggedhours.count(), 1)
        merge = ["services", "merge", service.pk, "--into", target.pk]
        result = self.wb(*merge, "--dry-run")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Dry run, nothing changed", result.output)
        self.assertTrue(Service.objects.filter(pk=service.pk).exists())
        result = self.wb(*merge)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(f"{service.pk} has been merged into", result.output)
        self.assertFalse(Service.objects.filter(pk=service.pk).exists())
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
        result = self.wb("hours", "search", "--hours-for-invoicing")
        self.assertNotIn("Wireframes", result.output)
        factories.LoggedHoursFactory.create(
            service=factories.ServiceFactory.create(project=project),
            hours=1,
            hours_for_invoicing=2,
            description="Sketches",
        )
        result = self.wb("hours", "search", "--hours-for-invoicing")
        self.assertIn("Sketches", result.output)
        self.assertIn("1.0 → 2.0", result.output)
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

    def test_invoiced_work(self):
        """Hours and services know what has been invoiced, invoices their
        services"""
        project = factories.ProjectFactory.create(owned_by=self.user)
        offer = factories.OfferFactory.create(
            project=project, offered_on=dt.date(2026, 9, 1)
        )
        service = factories.ServiceFactory.create(
            project=project,
            offer=offer,
            title="Design",
            effort_type="Design",
            effort_rate=200,
            external_reference="https://example.com/issues/1",
        )
        factories.LoggedHoursFactory.create(
            service=service, hours=3, description="Wireframes"
        )
        invoice = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            type=Invoice.SERVICES,
        )
        invoice.create_services_from_logbook([service])
        factories.LoggedHoursFactory.create(
            service=service, hours=2, description="Sketches"
        )

        result = self.wb("hours", "search", "--invoiced")
        self.assertIn("Wireframes", result.output)
        self.assertNotIn("Sketches", result.output)
        result = self.wb("hours", "search", "--not-invoiced", "--json")
        self.assertIn("Sketches", result.output)
        self.assertNotIn("Wireframes", result.output)
        self.assertIn('"invoice": null', result.output)

        result = self.wb(
            "services",
            "search",
            "--external-reference",
            "https://example.com/issues/1",
            "--json",
        )
        self.assertIn('"invoiced_hours": "3.0"', result.output)
        self.assertIn('"not_invoiced_hours": "2.0"', result.output)
        result = self.wb(
            "services", "search", "--external-reference", "https://example.com/"
        )
        self.assertNotIn("Design", result.output)

        result = self.wb("invoices", "show", invoice.pk)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Design", result.output)
        self.assertIn(offer.code, result.output)
        self.assertIn("600.00", result.output)

        result = self.wb("offers", "show", offer.pk)
        self.assertIn("2026-09-01", result.output)

        # External references, also of offers which have been sent
        offer.status = Offer.OFFERED
        offer.valid_until = dt.date(2026, 9, 30)
        offer.save()
        result = self.wb(
            "offers",
            "update",
            offer.pk,
            "--external-reference",
            "https://example.com/issues/1",
            "--external-reference",
            "https://example.com/pull/2",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        offer.refresh_from_db()
        self.assertEqual(
            offer.external_reference,
            "https://example.com/issues/1\nhttps://example.com/pull/2",
        )
        result = self.wb(
            "offers", "search", "--external-reference", "https://example.com/pull/2"
        )
        self.assertIn(offer.code, result.output)
        self.wb("offers", "update", offer.pk, "--external-reference", "")
        offer.refresh_from_db()
        self.assertEqual(offer.external_reference, "")

    def test_milestones(self):
        """Milestones are linked with offers through their external references"""
        project = factories.ProjectFactory.create(title="Relaunch", owned_by=self.user)
        factories.PostalAddressFactory.create(person=project.contact)
        offer = factories.OfferFactory.create(
            project=project, title="Relaunch | Phase 1"
        )
        base = "https://github.com/acme/web/milestone"
        github = {
            1: {"number": 1, "title": "Phase 1", "description": "", "state": "open"},
            2: {
                "number": 2,
                "title": "Extras",
                "description": "Ideas",
                "state": "open",
            },
        }
        calls = []

        def gh(path, *, method="GET", fields=None, paginate=False):
            calls.append((method, path, fields))
            for m in github.values():
                m |= {"html_url": f"{base}/{m['number']}", "open_issues": 0}
                m |= {"closed_issues": 0}
            if path.startswith("repos/acme/web/milestones?"):
                return list(github.values())
            number = int(path.rsplit("/", 1)[-1]) if path[-1].isdigit() else None
            if method == "POST":
                number = 3
                github[3] = {"number": 3, "state": "open", **fields}
                return gh("repos/acme/web/milestones/3")
            if method == "PATCH":
                github[number] |= fields
            return github[number]

        patcher = patch.object(wb.milestones, "gh", gh)
        patcher.start()
        self.addCleanup(patcher.stop)

        result = self.wb("milestones", "list", "acme/web", "--unlinked")
        self.assertIn("Phase 1", result.output)
        self.assertIn("Extras", result.output)

        # Link an existing milestone
        result = self.wb("milestones", "link", offer.pk, f"{base}/1", "--dry-run")
        self.assertEqual(result.exit_code, 0, result.output)
        offer.refresh_from_db()
        self.assertEqual(offer.external_reference, "")
        result = self.wb("milestones", "link", offer.pk, f"{base}/1")
        self.assertEqual(result.exit_code, 0, result.output)
        offer.refresh_from_db()
        self.assertEqual(offer.external_reference, f"{base}/1")
        self.assertIn(offer.code, github[1]["description"])
        result = self.wb("milestones", "list", "acme/web", "--unlinked")
        self.assertNotIn("Phase 1", result.output)

        # A service group for a milestone without offer
        other = factories.OfferFactory.create(project=project)
        result = self.wb("milestones", "link", other.pk, f"{base}/1")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("already linked", result.output)
        result = self.wb("milestones", "offer", project.pk, f"{base}/2")
        self.assertEqual(result.exit_code, 0, result.output)
        group = Offer.objects.get(external_reference=f"{base}/2")
        self.assertEqual(group.status, Offer.SERVICE_GROUP)
        self.assertEqual(group.title, "Relaunch | Extras")
        self.assertEqual(group.description, "Ideas")
        self.assertIn(group.code, github[2]["description"])

        # A new milestone for an offer
        result = self.wb(
            "milestones", "create", other.pk, "acme/web", "--title", "Extras"
        )
        self.assertEqual(result.exit_code, 1)
        self.assertIn("already has the milestone", result.output)
        result = self.wb(
            "milestones", "create", other.pk, "acme/web", "--title", "Phase 2"
        )
        self.assertEqual(result.exit_code, 0, result.output)
        other.refresh_from_db()
        self.assertEqual(other.external_reference, f"{base}/3")
        self.assertIn(other.code, github[3]["description"])
        self.assertEqual(
            [call[0] for call in calls if call[0] != "GET"], ["PATCH", "PATCH", "POST"]
        )

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

    def test_ignore_warnings(self):
        """Absences, closing deals and new people ignore warnings by code"""
        absence = [
            "absences",
            "create",
            "--starts-on",
            in_days(400),
            "--days",
            1,
            "--reason",
            "vacation",
        ]
        result = self.wb(*absence)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("--ignore-warning impressive-planning-skills", result.output)
        result = self.wb(*absence, "--ignore-warning", "impressive-planning-skills")
        self.assertEqual(result.exit_code, 0, result.output)

        deal = factories.DealFactory.create(owned_by=self.user)
        factories.ClosingTypeFactory.create(title="Won", represents_a_win=True)
        close = [
            "deals",
            "close",
            deal.pk,
            "accepted",
            "--closing-type",
            "won",
            "--closed-on",
            in_days(100),
        ]
        result = self.wb(*close)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("--ignore-warning closed-in-future", result.output)
        result = self.wb(*close, "--ignore-warning", "closed-in-future")
        self.assertEqual(result.exit_code, 0, result.output)
        deal.refresh_from_db()
        self.assertEqual(deal.status, Deal.ACCEPTED)

        person = self.file("given_name: Hans\nfamily_name: Muster\nsalutation: Hi\n")
        result = self.wb("people", "create", person)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("--ignore-warning short-salutation", result.output)
        result = self.wb(
            "people", "create", person, "--ignore-warning", "short-salutation"
        )
        self.assertEqual(result.exit_code, 0, result.output)

        # Their deals, projects and invoices would need a new contact
        duplicate = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )
        factories.DealFactory.create(customer=duplicate.organization, contact=duplicate)
        keep = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )
        merge = ["people", "merge", duplicate.pk, "--into", keep.pk]
        result = self.wb(*merge)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("--ignore-warning other-organization", result.output)
        result = self.wb(*merge, "--ignore-warning", "other-organization")
        self.assertEqual(result.exit_code, 0, result.output)

    def test_people_duplicates(self):
        """Possible duplicates are listed in groups"""
        keep = factories.PersonFactory.create(given_name="Anna", family_name="Muster")
        keep.emailaddresses.create(email="anna@example.com")
        duplicate = factories.PersonFactory.create(
            given_name="Anna", family_name="Muster"
        )
        factories.PersonFactory.create(given_name="Bea", family_name="Muster")

        result = self.wb("people", "duplicates")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("anna@example.com", result.output)
        self.assertNotIn("Bea", result.output)

        result = self.wb("people", "duplicates", "--json")
        data = json.loads(result.output)
        self.assertEqual(data["count"], 1)
        self.assertEqual(
            [person["id"] for person in data["items"][0]["people"]],
            [keep.pk, duplicate.pk],
        )

    def test_organizations(self):
        """Organizations are searched, changed and merged"""
        former = factories.UserFactory.create(_short_name="old", is_active=False)
        keep = factories.OrganizationFactory.create(
            name="Beispiel AG", primary_contact=former
        )
        factories.PersonFactory.create(organization=keep)
        duplicate = factories.OrganizationFactory.create(name="Beispiel")
        person = factories.PersonFactory.create(organization=duplicate)

        result = self.wb("organizations", "search", "--primary-contact", "old")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Beispiel AG", result.output)
        result = self.wb("organizations", "search", "--primary-contact", "nobody")
        self.assertEqual(result.exit_code, 1)

        result = self.wb(
            "organizations", "merge", duplicate.pk, "--into", keep.pk, "--dry-run"
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("would be merged", result.output)
        self.assertTrue(Organization.objects.filter(pk=duplicate.pk).exists())
        result = self.wb("organizations", "merge", duplicate.pk, "--into", duplicate.pk)
        self.assertEqual(result.exit_code, 1)
        result = self.wb("organizations", "merge", duplicate.pk, "--into", keep.pk)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertFalse(Organization.objects.filter(pk=duplicate.pk).exists())
        person.refresh_from_db()
        self.assertEqual(person.organization, keep)
        keep.refresh_from_db()
        # The active primary contact of the duplicate replaced the inactive one
        self.assertEqual(keep.primary_contact, duplicate.primary_contact)

        result = self.wb("organizations", "update", keep.pk, "--primary-contact", "old")
        self.assertEqual(result.exit_code, 1)
        keep.people.update(is_archived=True)
        result = self.wb("organizations", "search", "--without-active-people")
        self.assertIn("Beispiel AG", result.output)
        result = self.wb("organizations", "update", keep.pk, "--email", "nope")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("email", result.output)
        result = self.wb(
            "organizations", "update", keep.pk, "--email", "info@example.com"
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("info@example.com", result.output)
        result = self.wb("organizations", "update", keep.pk, "--archive")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("(archived)", result.output)
        result = self.wb("organizations", "search", "--without-active-people")
        self.assertNotIn("Beispiel AG", result.output)

    def test_shared_emails(self):
        """Generic addresses of several people move to the organization"""
        organization = factories.OrganizationFactory.create()
        anna, bea = (
            factories.PersonFactory.create(organization=organization, given_name=name)
            for name in ["Anna", "Bea"]
        )
        anna.emailaddresses.create(email="info@example.com")
        bea.emailaddresses.create(email="Info@Example.com ")
        bea.emailaddresses.create(email="bea@example.com")
        # Other organizations and archived people don't count
        factories.PersonFactory.create().emailaddresses.create(email="info@example.com")
        factories.PersonFactory.create(
            organization=organization, is_archived=True
        ).emailaddresses.create(email="bea@example.com")

        result = self.wb("people", "shared-emails", "--json")
        data = json.loads(result.output)
        self.assertEqual(
            [(row["email"], [p["id"] for p in row["people"]]) for row in data["items"]],
            [("info@example.com", [anna.pk, bea.pk])],
        )
        self.assertIn("Anna", self.wb("people", "shared-emails").output)

        self.wb(
            "organizations", "update", organization.pk, "--email", "info@example.com"
        )
        result = self.wb(
            "people", "update", anna.pk, "--remove-email", "INFO@example.com"
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(list(anna.emailaddresses.all()), [])
        # Bea still has the organization's address
        result = self.wb("people", "shared-emails", "--json")
        self.assertEqual(
            [
                (row["is_organization_email"], [p["id"] for p in row["people"]])
                for row in json.loads(result.output)["items"]
            ],
            [(True, [bea.pk])],
        )
        result = self.wb("people", "update", bea.pk, "--remove-email", "x@example.com")
        self.assertEqual(result.exit_code, 1)
        result = self.wb(
            "people", "update", bea.pk, "--remove-email", "info@example.com"
        )
        self.assertEqual(
            [e.email for e in bea.emailaddresses.all()], ["bea@example.com"]
        )
        self.assertEqual(
            json.loads(self.wb("people", "shared-emails", "--json").output)["count"], 0
        )

        # The central address isn't added to people again
        result = self.wb(
            "people",
            "add-details",
            anna.pk,
            self.file("email_addresses:\n  - email: info@example.com\n"),
        )
        self.assertEqual(result.exit_code, 1)
        self.assertIn("The central address of", result.output)

    def test_organization_postal_addresses(self):
        """Organizations with different addresses are found, an address is
        changed for several people at once"""
        organization = factories.OrganizationFactory.create(name="Beispiel AG")
        anna, bea, carl = (
            factories.PersonFactory.create(organization=organization, given_name=name)
            for name in ["Anna", "Bea", "Carl"]
        )
        old = {"street": "Altweg", "postal_code": "8000", "city": "Zürich"}
        address = anna.postaladdresses.create(**old)
        bea.postaladdresses.create(**old)
        carl.postaladdresses.create(**old, house_number="2")
        other = factories.OrganizationFactory.create(name="Anders AG")
        factories.PersonFactory.create(organization=other).postaladdresses.create(**old)

        result = self.wb("organizations", "search", "--several-postal-addresses")
        self.assertIn("Beispiel AG", result.output)
        self.assertNotIn("Anders AG", result.output)

        result = self.wb("organizations", "show", organization.pk)
        self.assertIn("Altweg 2, 8000 Zürich", result.output)
        self.assertIn(f"Bea Nachname ({bea.pk})", result.output)

        change = [
            "organizations",
            "change-address",
            organization.pk,
            "--address",
            address.pk,
            "--house-number",
            "2",
        ]
        result = self.wb(*change, "--person", anna.pk, "--dry-run")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(anna.postaladdresses.get().house_number, "")
        result = self.wb(*change, "--person", anna.pk, "--person", bea.pk)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            [a.house_number for p in [anna, bea] for a in p.postaladdresses.all()],
            ["2", "2"],
        )
        result = self.wb("organizations", "search", "--several-postal-addresses")
        self.assertNotIn("Beispiel AG", result.output)

        result = self.wb(*change[:4], "0", "--city", "Bern")
        self.assertEqual(result.exit_code, 1)
        result = self.wb(*change[:5], "--city", "")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("city", result.output)

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

    def test_send_reminder(self):
        """Reminders are previewed without a recipient"""
        invoice = factories.InvoiceFactory.create(
            status=Invoice.SENT, invoiced_on=in_days(-60), due_on=in_days(-30)
        )
        invoice.contact.emailaddresses.create(email="billing@example.com")
        result = self.wb("invoices", "send-reminder", invoice.contact.pk)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("billing@example.com", result.output)
        self.assertIn("choose a recipient with --to", result.output)

        result = self.wb(
            "invoices",
            "send-reminder",
            invoice.contact.pk,
            "--to",
            "billing@example.com",
        )
        self.assertIn("The reminder has been sent.", result.output)

    def test_choices_match_the_server(self):
        """Choices the CLI offers are keys of the server, they don't drift
        apart unnoticed"""
        server = {
            ("absences", "reason"): "absence_reason",
            ("invoices", "status"): "invoice_status",
            ("invoices", "type"): "invoice_type",
            ("deals", "status"): "deal_status",
            ("deals", "probability"): "deal_probability",
            ("offers", "status"): "offer_status",
            ("projects", "type"): "project_type",
        }
        checked = set()

        def walk(command, path):
            for param in command.params:
                if isinstance(param.type, click.Choice) and (
                    name := server.get((
                        path[0] if path else "",
                        param.name.rstrip("_"),
                    ))
                ):
                    with self.subTest(command=" ".join(path), param=param.name):
                        self.assertLessEqual(set(param.type.choices), set(KEYS[name]))
                    checked.add(name)
            for name, sub in getattr(command, "commands", {}).items():
                walk(sub, [*path, name])

        walk(wb.cli, [])
        self.assertEqual(checked, set(server.values()))

    def test_show_by_code(self):
        project = factories.ProjectFactory.create(title="Relaunch")
        offer = factories.OfferFactory.create(project=project, title="Phase 1")
        result = self.wb("projects", "show", project.code)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Relaunch", result.output)
        self.assertIn("Phase 1", result.output)
        result = self.wb("offers", "show", offer.code)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Phase 1", result.output)

    @override_settings(FEATURES={FEATURES.CAMPAIGNS: F.ALWAYS})
    def test_campaigns(self):
        campaign = factories.CampaignFactory.create(title="Relaunch")
        factories.ProjectFactory.create(campaign=campaign)
        result = self.wb("campaigns")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Relaunch", result.output)
        result = self.wb("campaigns", "search", "nothing", "--include-closed")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertNotIn("Relaunch", result.output)

    def test_invoices_owned_by_and_type(self):
        factories.InvoiceFactory.create(
            owned_by=self.user, type="credit", subtotal=-10, title="Refund"
        )
        result = self.wb(
            "invoices",
            "search",
            "--owned-by",
            self.user.get_short_name(),
            "--type",
            "credit",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Refund", result.output)

    def test_deal_value_types_and_attributes(self):
        factories.ValueTypeFactory.create(title="Design")
        group = AttributeGroup.objects.create(title="Source")
        group.attributes.create(title="Referral")
        result = self.wb("deals", "value-types")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Design", result.output)
        result = self.wb("deals", "attributes")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Source", result.output)
        self.assertIn("Referral", result.output)
        factories.ClosingTypeFactory.create(title="Too expensive")
        result = self.wb("deals", "closing-types")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Too expensive", result.output)
        self.assertIn("declined", result.output)
        factories.service_types()
        result = self.wb("services", "types")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("consulting", result.output)

    def test_deals(self):
        """Searching, creating, updating, closing and reopening deals"""
        project = factories.ProjectFactory.create(owned_by=self.user)
        deal = factories.DealFactory.create(owned_by=self.user, title="Big deal")
        self.assertIn("Big deal", self.wb("deals", "search").output)
        self.assertNotIn(
            "Big deal",
            self.wb("deals", "search", "--contributor", self.user._short_name).output,
        )
        deal.contributions.create(user=self.user)
        self.assertIn(
            "Big deal",
            self.wb("deals", "search", "--contributor", self.user._short_name).output,
        )
        for key in [deal.pk, deal.code]:
            result = self.wb("deals", "show", key)
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Big deal", result.output)
            self.assertIn(f"{self.user.get_short_name()} (", result.output)
        result = self.wb("deals", "show", deal.pk, "--json")
        self.assertEqual(json.loads(result.output)["id"], deal.pk)

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
        other = factories.UserFactory.create(_short_name="zz")
        result = self.wb(
            "deals",
            "update",
            open_deal.pk,
            "--contribution",
            "zz=50",
            "--contribution",
            f"{self.user.get_short_name()}=100",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("zz (50)", result.output)
        self.assertEqual(open_deal.contributions.get(user=other).weight, 50)
        result = self.wb("deals", "update", open_deal.pk, "--contribution", "zz=30")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("0, 50 or 100", result.output)
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

    def test_deal_offers(self):
        """Offers are linked to deals and unlinked by ID or code"""
        offer = factories.OfferFactory.create(status=Offer.OFFERED)
        other = factories.OfferFactory.create(status=Offer.OFFERED)
        deal = factories.DealFactory.create(
            owned_by=self.user, customer=offer.project.customer
        )
        result = self.wb("deals", "offers", "add", deal.pk, offer.code, "--dry-run")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(offer.code, result.output)
        self.assertIn("Dry run", result.output)
        self.assertFalse(deal.related_offers.exists())

        result = self.wb("deals", "offers", "add", deal.pk, offer.code, other.pk)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("not of the deal's customer", result.output)
        self.assertFalse(deal.related_offers.exists())
        result = self.wb(
            "deals",
            "offers",
            "add",
            deal.pk,
            offer.code,
            other.pk,
            "--ignore-warning",
            "other-customer",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(set(deal.related_offers.all()), {offer, other})

        # Dry runs show the result
        result = self.wb("deals", "offers", "remove", deal.pk, other.code, "--dry-run")
        self.assertNotIn(other.code, result.output)
        self.assertEqual(deal.related_offers.count(), 2)
        result = self.wb("deals", "offers", "remove", deal.pk, other.code)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(deal.related_offers.get(), offer)

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

    def test_squeeze_outreach(self):
        outreach = InternalType.objects.create(
            name="Outreach", percentage=10, is_outreach=True
        )
        factories.LoggedHoursFactory.create(
            service=factories.ServiceFactory.create(
                project=factories.ProjectFactory.create(
                    type=Project.INTERNAL, internal_type=outreach
                )
            ),
            rendered_by=self.user,
            hours=4,
        )
        deal = factories.DealFactory.create(
            owned_by=self.user, status=Deal.ACCEPTED, closed_on=dt.date.today()
        )
        deal.values.create(type=factories.ValueTypeFactory.create(), value=1000)
        deal.save()
        deal.contributions.create(user=self.user, weight=100)

        result = self.wb("reports", "squeeze", "--period", "this-month")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Outreach", result.output)
        self.assertIn("Accepted deals  1000.00", result.output)
        self.assertIn("Per hour        250.00", result.output)
        # Only the total, no figures per person
        self.assertEqual(result.output.count("Per hour"), 1)

    def test_write_config(self):
        """The configuration with the tokens is only readable by its owner,
        also while being written, and replaced atomically"""
        config = self.directory / "config" / "workbench.toml"
        replace = os.replace
        modes = []

        def checked_replace(src, dst):
            modes.append(os.stat(src).st_mode & 0o777)
            replace(src, dst)

        with (
            patch.object(wb.core, "CONFIG", config),
            patch.object(wb.core.os, "replace", checked_replace),
        ):
            wb.core.save_config("https://a.example.com", "secret")
            config.chmod(0o644)
            inode = config.stat().st_ino
            wb.core.save_config("https://b.example.com", "other")
        # Private before it becomes visible, replaced instead of overwritten
        self.assertEqual(modes, [0o600, 0o600])
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        self.assertNotEqual(config.stat().st_ino, inode)

        with (
            patch.object(wb.core, "CONFIG", config),
            patch.object(wb.core.os, "replace", side_effect=OSError),
            self.assertRaises(OSError),
        ):
            wb.core.save_config("https://c.example.com", "third")
        # The old configuration is intact, no temporary files are left
        self.assertEqual(list(config.parent.iterdir()), [config])
        self.assertIn("b.example.com", config.read_text())
        self.assertNotIn("c.example.com", config.read_text())

    def test_announce_installation(self):
        """Commands say when they don't use the current installation"""
        result = self.wb("me")
        self.assertNotIn("Using http://testserver", result.output)

        wb.core.CONFIG.write_text(
            'current = "https://other.example.com"\n'
            '[installations."https://other.example.com"]\ntoken = "other"\n'
        )
        result = self.wb("me")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            result.output.count(
                "Using http://testserver (WORKBENCH_URL), not the current"
                " https://other.example.com."
            ),
            1,
        )
        # Not part of the data
        self.assertNotIn("Using", self.wb("me", "--json").stdout)

        result = self.wb("-i", "testserver", "me")
        self.assertIn("Using http://testserver (--installation)", result.output)

    def test_offer_guidelines(self):
        """Private offer guidelines come from a file configured per installation"""
        wb.core.CONFIG.write_text(
            'current = "http://testserver"\n'
            '[installations."http://testserver"]\ntoken = "secret"\n'
            '[installations."https://other.example.com"]\ntoken = "other"\n'
        )
        result = self.wb("offers", "guidelines")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("No offer guidelines configured", result.output)

        guidelines = self.directory / "Guidelines.md"
        result = self.wb("offers", "guidelines", "--set", guidelines)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("does not exist", result.output)

        guidelines.write_text("# Rules\n\nProject management is 25 %.\n")
        result = self.wb("offers", "guidelines", "--set", guidelines)
        self.assertEqual(result.exit_code, 0, result.output)
        config = wb.core.read_config()["installations"]
        self.assertEqual(
            config["http://testserver"]["offer_guidelines"], str(guidelines)
        )
        self.assertNotIn("offer_guidelines", config["https://other.example.com"])

        result = self.wb("offers", "guidelines")
        self.assertEqual(result.stdout, "# Rules\n\nProject management is 25 %.\n")
        self.assertIn(
            f"Offer guidelines for http://testserver from {guidelines}",
            result.stderr,
        )

        # Logging in again keeps the setting
        wb.core.save_config("http://testserver", "new", "write")
        config = wb.core.read_config()["installations"]["http://testserver"]
        self.assertEqual(config["offer_guidelines"], str(guidelines))
        self.assertEqual(config["token"], "new")

        guidelines.unlink()
        result = self.wb("offers", "guidelines")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("does not exist", result.output)

        result = self.wb("offers", "guidelines", "--clear")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertNotIn("offer_guidelines", wb.core.CONFIG.read_text())

        # --installation selects another installation for one command, it
        # takes precedence over WORKBENCH_URL
        guidelines.write_text("Other rules\n")
        result = self.wb("-i", "other", "offers", "guidelines", "--set", guidelines)
        self.assertEqual(result.exit_code, 0, result.output)
        config = wb.core.read_config()["installations"]
        self.assertEqual(
            config["https://other.example.com"]["offer_guidelines"], str(guidelines)
        )
        self.assertNotIn("offer_guidelines", config["http://testserver"])
        result = self.wb("--installation", "nope", "offers", "guidelines")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("No installations match 'nope'", result.output)

    def test_key_data_and_cash_data(self):
        project = factories.ProjectFactory.create(owned_by=self.user)
        factories.InvoiceFactory.create(project=project, customer=project.customer)
        result = self.wb("reports", "key-data", "--month", "2026-01")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Key data 2026-01", result.output)
        self.assertIn("Deals funnel", result.output)
        result = self.wb("reports", "key-data", "--month", "2026-01", "--json")
        self.assertIn('"month": "2026-01"', result.output)

        with override_settings(
            FEATURES={
                FEATURES.CONTROLLING: F.ALWAYS,
                FEATURES.DEALS: F.NEVER,
                FEATURES.PRODUCTIVITY: F.NEVER,
            }
        ):
            result = self.wb("reports", "key-data", "--month", "2026-01")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Gross margin", result.output)
        self.assertNotIn("Squeeze", result.output)
        self.assertNotIn("Deals funnel", result.output)

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
        self.assertIn("planned,", result.output)
        result = self.wb("reports", "working-time", "--weekly")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(monday().isoformat(), result.output)
        result = self.wb("reports", "working-time", "--all")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Other absences planned", result.output)
        self.assertIn(self.user.get_short_name(), result.output)

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
        self.assertIn(cli_version.UPGRADE, result.output)

        wb.core._check_version.cache_clear()
        with patch.object(cli_version, "LATEST", "0.0.1"):
            result = self.wb("me")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("This Workbench is older than your wb", result.output)

        with patch.object(cli_version, "MINIMUM", (99, 0, 0)):
            result = self.wb("me")
        self.assertEqual(result.exit_code, 1)
        self.assertIn(cli_version.UPGRADE, result.output)

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
        self.assertNotIn("services", complete(["offers"], ""))
        self.assertEqual(
            complete(["services"], ""),
            [
                "create",
                "delete",
                "merge",
                "reassign-logbook",
                "reorder",
                "search",
                "types",
                "update",
            ],
        )
        self.assertIn("--clear-cost", complete(["services", "update"], "--"))
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
