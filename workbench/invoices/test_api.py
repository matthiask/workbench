import datetime as dt

from django.test import TestCase
from django.test.utils import override_settings
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.invoices.models import Invoice
from workbench.tools.validation import in_days


class InvoicesAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def test_list(self):
        """Invoices can be filtered"""
        project = factories.ProjectFactory.create()
        sent = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            status=Invoice.SENT,
            invoiced_on=in_days(-30),
            due_on=in_days(-20),
            subtotal=100,
        )
        draft = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            invoiced_on=None,
        )
        paid = factories.InvoiceFactory.create(
            status=Invoice.PAID,
            invoiced_on=dt.date(2025, 1, 1),
            closed_on=dt.date(2025, 2, 1),
        )
        self.client.force_login(project.owned_by)

        def ids(query=""):
            return {i["id"] for i in self.client.get(f"/api/invoices/{query}").json()}

        self.assertEqual(ids(), {sent.pk, draft.pk, paid.pk})
        self.assertEqual(ids(f"?project={project.pk}"), {sent.pk, draft.pk})
        self.assertEqual(ids("?open=true"), {sent.pk, draft.pk})
        self.assertEqual(ids("?overdue=true"), {sent.pk})
        self.assertEqual(ids("?status=paid"), {paid.pk})
        self.assertEqual(ids("?invoiced_since=2026-01-01"), {sent.pk})
        self.assertEqual(ids(f"?q={paid.code}"), {paid.pk})
        self.assertEqual(self.client.get("/api/invoices/?status=nope").status_code, 422)

        data = self.client.get(f"/api/invoices/{sent.pk}/").json()
        self.assertEqual(data["code"], sent.code)
        self.assertEqual(data["project"]["code"], project.code)
        self.assertEqual(
            data["project"]["url"], f"http://testserver{project.get_absolute_url()}"
        )
        self.assertEqual(data["total_excl_tax"], "100.00")
        self.assertEqual(data["url"], f"http://testserver{sent.get_absolute_url()}")

    def test_projected_invoices(self):
        """The planned invoicing of a project"""
        project = factories.ProjectFactory.create()
        factories.ProjectedInvoiceFactory.create(
            project=project,
            invoiced_on=in_days(30),
            gross_margin=1000,
            description="Kick-off",
        )
        self.client.force_login(project.owned_by)

        data = self.client.get(f"/api/projects/{project.pk}/projected-invoices/").json()
        self.assertEqual(
            data,
            [
                {
                    "project": {
                        "id": project.pk,
                        "code": project.code,
                        "title": project.title,
                        "url": f"http://testserver{project.get_absolute_url()}",
                    },
                    "invoiced_on": in_days(30).isoformat(),
                    "gross_margin": "1000.00",
                    "description": "Kick-off",
                }
            ],
        )

    def test_projected_invoices_search(self):
        """The planned invoicing of all projects can be filtered"""
        later = factories.ProjectedInvoiceFactory.create(
            invoiced_on=in_days(60), gross_margin=1000
        )
        sooner = factories.ProjectedInvoiceFactory.create(
            invoiced_on=in_days(30), gross_margin=2000
        )
        self.client.force_login(later.project.owned_by)

        def rows(query=""):
            return [
                (row["project"]["code"], row["gross_margin"])
                for row in self.client.get(f"/api/projected-invoices/{query}").json()
            ]

        self.assertEqual(
            rows(),
            [(sooner.project.code, "2000.00"), (later.project.code, "1000.00")],
        )
        self.assertEqual(
            rows(f"?project={later.project.pk}"),
            [(later.project.code, "1000.00")],
        )
        self.assertEqual(
            rows(f"?customer={sooner.project.customer_id}"),
            [(sooner.project.code, "2000.00")],
        )
        self.assertEqual(
            rows(f"?invoiced_since={in_days(45).isoformat()}"),
            [(later.project.code, "1000.00")],
        )
        self.assertEqual(
            rows(f"?invoiced_until={in_days(45).isoformat()}"),
            [(sooner.project.code, "2000.00")],
        )

    @override_settings(FEATURES={FEATURES.CONTROLLING: F.NEVER})
    def test_reminders(self):
        """Overdue invoices per customer and contact, available without the
        controlling feature like in the web interface"""
        project = factories.ProjectFactory.create()
        invoice = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            status=Invoice.SENT,
            invoiced_on=in_days(-60),
            due_on=in_days(-30),
            subtotal=100,
        )
        factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            status=Invoice.SENT,
            invoiced_on=in_days(-60),
            due_on=in_days(-30),
            postpone_reminders_until=in_days(10),
        )
        factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            status=Invoice.SENT,
            invoiced_on=in_days(-20),
            due_on=in_days(-10),
        )
        self.client.force_login(project.owned_by)

        [group] = self.client.get("/api/invoices/reminders/").json()
        self.assertEqual(group["customer"]["id"], project.customer_id)
        self.assertEqual(group["contact"]["id"], project.contact_id)
        self.assertEqual(group["total_excl_tax"], "100.00")
        [row] = group["invoices"]
        self.assertEqual(row["id"], invoice.id)
        self.assertEqual(row["days_overdue"], 30)
        self.assertIsNone(row["last_reminded_on"])

        self.assertEqual(self.client.get("/api/invoices/").status_code, 403)
