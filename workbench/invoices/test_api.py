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
            return {
                i["id"]
                for i in self.client.get(f"/api/invoices/{query}").json()["items"]
            }

        self.assertEqual(ids(), {sent.pk, draft.pk, paid.pk})
        self.assertEqual(ids(f"?project={project.pk}"), {sent.pk, draft.pk})
        self.assertEqual(ids("?open=true"), {sent.pk, draft.pk})
        self.assertEqual(ids("?overdue=true"), {sent.pk})
        self.assertEqual(ids("?status=paid"), {paid.pk})
        self.assertEqual(ids("?since=2026-01-01"), {sent.pk})
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

        data = self.client.get(f"/api/projected-invoices/?project={project.pk}")
        data = data.json()["items"]
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
                for row in self.client.get(f"/api/projected-invoices/{query}").json()[
                    "items"
                ]
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
            rows(f"?since={in_days(45).isoformat()}"),
            [(later.project.code, "1000.00")],
        )
        self.assertEqual(
            rows(f"?until={in_days(45).isoformat()}"),
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

    def test_recurring_invoices(self):
        """Recurring invoices which still renew by default"""
        user = factories.UserFactory.create(_short_name="ab")
        hosting = factories.RecurringInvoiceFactory.create(
            title="Hosting", owned_by=user, subtotal=1200
        )
        ended = factories.RecurringInvoiceFactory.create(
            title="Support", starts_on=in_days(-400), ends_on=in_days(-10)
        )
        self.client.force_login(user)

        def ids(query=""):
            data = self.client.get(f"/api/recurring-invoices/{query}").json()
            return [row["id"] for row in data["items"]]

        self.assertEqual(ids(), [hosting.pk])
        self.assertEqual(ids("?status=closed"), [ended.pk])
        self.assertEqual(set(ids("?status=all")), {hosting.pk, ended.pk})
        self.assertEqual(ids("?status=all&owned_by=AB"), [hosting.pk])
        self.assertEqual(ids(f"?status=all&customer={ended.customer_id}"), [ended.pk])
        self.assertEqual(ids("?q=hosting"), [hosting.pk])

        data = self.client.get("/api/recurring-invoices/").json()["items"][0]
        self.assertEqual(data["periodicity"], "yearly")
        self.assertEqual(data["owned_by"], "ab")

    def test_mark_reminded(self):
        """Overdue invoices are marked as reminded today"""
        invoice = factories.InvoiceFactory.create(
            status=Invoice.SENT, invoiced_on=in_days(-60), due_on=in_days(-30)
        )
        other = factories.InvoiceFactory.create(
            status=Invoice.SENT, invoiced_on=in_days(-5), due_on=in_days(25)
        )
        self.client.force_login(invoice.owned_by)
        url = "/api/invoices/reminders/"

        response = self.client.post(
            f"{url}?dry_run=true",
            {"invoices": [invoice.pk]},
            content_type="application/json",
        )
        [group] = response.json()
        self.assertEqual(
            group["invoices"][0]["last_reminded_on"], dt.date.today().isoformat()
        )
        invoice.refresh_from_db()
        self.assertIsNone(invoice.last_reminded_on)

        response = self.client.post(
            url, {"invoices": [invoice.pk, other.pk]}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn(str(other.pk), response.content.decode())

        response = self.client.post(
            url, {"invoices": [invoice.pk]}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        invoice.refresh_from_db()
        self.assertEqual(invoice.last_reminded_on, dt.date.today())

    def test_postpone_reminders(self):
        """Reminders of sent invoices are postponed for up to 60 days, more
        than 30 days have to be confirmed"""
        invoice = factories.InvoiceFactory.create(
            status=Invoice.SENT, invoiced_on=in_days(-60), due_on=in_days(-30)
        )
        self.client.force_login(invoice.owned_by)
        url = f"/api/invoices/{invoice.pk}/postpone-reminders/"

        def post(data):
            return self.client.post(url, data, content_type="application/json")

        response = post({"until": in_days(10).isoformat()})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json()["postpone_reminders_until"], in_days(10).isoformat()
        )
        self.assertEqual(self.client.get("/api/invoices/reminders/").json(), [])

        response = post({"until": in_days(40).isoformat()})
        self.assertEqual(response.status_code, 422)
        self.assertIn("Are you sure?", response.content.decode())
        response = post({"until": in_days(40).isoformat(), "confirm": True})
        self.assertEqual(response.status_code, 200, response.content)
        response = post({"until": in_days(70).isoformat(), "confirm": True})
        self.assertEqual(response.status_code, 422)

        response = post({"until": None})
        invoice.refresh_from_db()
        self.assertIsNone(invoice.postpone_reminders_until)

        invoice.status = Invoice.PAID
        invoice.closed_on = dt.date.today()
        invoice.save()
        self.assertEqual(post({"until": None}).status_code, 409)
