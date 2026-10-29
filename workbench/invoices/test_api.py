import datetime as dt

from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories
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
        self.assertEqual(self.client.get("/api/invoices/?status=nope").status_code, 422)

        data = self.client.get(f"/api/invoices/{sent.pk}/").json()
        self.assertEqual(data["code"], sent.code)
        self.assertEqual(data["project"], project.code)
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
                    "invoiced_on": in_days(30).isoformat(),
                    "gross_margin": "1000.00",
                    "description": "Kick-off",
                }
            ],
        )
