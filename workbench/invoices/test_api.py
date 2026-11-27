import datetime as dt
from unittest import mock
from unittest.mock import ANY

from django.conf import settings
from django.core import mail
from django.test import TestCase
from django.test.utils import override_settings
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.invoices.models import Invoice
from workbench.reporting.models import FreezeDate
from workbench.tools.formats import local_date_format
from workbench.tools.validation import in_days


ADDRESS = "Beispiel AG\nHans Muster\nMusterweg 1\n8000 Zürich"


class InvoicesAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def test_list_owned_by_and_type(self):
        """Invoices are filtered by their owner and their type"""
        user = factories.UserFactory.create(_short_name="ab")
        mine = factories.InvoiceFactory.create(owned_by=user, type=Invoice.FIXED)
        factories.InvoiceFactory.create(type=Invoice.FIXED)
        credit = factories.InvoiceFactory.create(
            owned_by=user, type=Invoice.CREDIT, subtotal=-10
        )
        self.client.force_login(user)

        def ids(**params):
            return [
                row["id"]
                for row in self.client.get("/api/invoices/", params).json()["items"]
            ]

        self.assertEqual(sorted(ids(owned_by="AB")), sorted([mine.pk, credit.pk]))
        self.assertEqual(ids(owned_by="ab", type="credit"), [credit.pk])

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

    def test_detail_services(self):
        """Invoices for services list their services with the offers"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        service = factories.ServiceFactory.create(
            project=project,
            offer=offer,
            title="Design",
            effort_type="Design",
            effort_rate=200,
        )
        factories.LoggedHoursFactory.create(service=service, hours=3)
        invoice = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            type=Invoice.SERVICES,
        )
        invoice.create_services_from_logbook([service])
        self.client.force_login(project.owned_by)

        data = self.client.get(f"/api/invoices/{invoice.pk}/").json()
        self.assertEqual(len(data["services"]), 1)
        line = data["services"][0]
        self.assertEqual(
            {
                key: line[key]
                for key in [
                    "title",
                    "effort_hours",
                    "effort_rate",
                    "service_cost",
                    "project_service_id",
                    "offer_id",
                    "offer",
                ]
            },
            {
                "title": "Design",
                "effort_hours": "3.0",
                "effort_rate": "200.00",
                "service_cost": "600.00",
                "project_service_id": service.pk,
                "offer_id": offer.pk,
                "offer": offer.code,
            },
        )

        fixed = factories.InvoiceFactory.create(subtotal=100)
        data = self.client.get(f"/api/invoices/{fixed.pk}/").json()
        self.assertEqual(data["services"], [])

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
                    "id": ANY,
                    "project": {
                        "id": project.pk,
                        "code": project.code,
                        "title": project.title,
                        "url": f"http://testserver{project.get_absolute_url()}",
                        "customer": {
                            "id": project.customer.pk,
                            "name": project.customer.name,
                        },
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
        self.assertEqual(set(ids("?include_closed=true")), {hosting.pk, ended.pk})
        self.assertEqual(ids("?include_closed=true&owned_by=AB"), [hosting.pk])
        self.assertEqual(
            ids(f"?include_closed=true&customer={ended.customer_id}"), [ended.pk]
        )
        self.assertEqual(ids("?q=hosting"), [hosting.pk])

        data = self.client.get("/api/recurring-invoices/").json()["items"][0]
        self.assertEqual(data["periodicity"], "yearly")
        self.assertEqual(data["owned_by"], "ab")

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

    @mock.patch.object(
        settings.WORKBENCH, "BOOKKEEPING_EMAIL", "bookkeeping@example.com"
    )
    @override_settings(
        FEATURES={FEATURES.CONTROLLING: F.ALWAYS, FEATURES.BOOKKEEPING: F.NEVER}
    )
    def test_create_drafts(self):
        """Invoices in preparation are created like in the web interface,
        with its defaults"""
        project = factories.ProjectFactory.create(title="Relaunch")
        factories.PostalAddressFactory.create(person=project.contact)
        self.client.force_login(project.owned_by)

        def create(data, query=""):
            return self.client.post(
                f"/api/invoices/{query}", data, content_type="application/json"
            )

        response = create({"project": project.pk, "subtotal": 2500}, "?dry_run=true")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["id"], None)
        self.assertEqual(Invoice.objects.count(), 0)

        response = create({"project": project.pk, "subtotal": 2500})
        self.assertEqual(response.status_code, 200, response.content)
        invoice = Invoice.objects.get(pk=response.json()["id"])
        self.assertEqual(
            (invoice.status, invoice.type, invoice.title, invoice.subtotal),
            (Invoice.IN_PREPARATION, Invoice.FIXED, "Relaunch", 2500),
        )
        self.assertEqual(invoice.contact, project.contact)
        self.assertEqual(invoice.owned_by, project.owned_by)
        self.assertIn(project.contact.family_name, invoice.postal_address)

        # The offer's services
        offer = factories.OfferFactory.create(project=project, title="Phase 1")
        factories.ServiceFactory.create(
            project=project, offer=offer, title="Design", cost=1000
        )
        factories.ServiceFactory.create(
            project=project, offer=offer, title="Hosting", cost=500
        )
        response = create({"offer": offer.pk})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["title"], "Relaunch - Phase 1")
        self.assertEqual(data["total_excl_tax"], "1500.00")
        self.assertEqual([s["title"] for s in data["services"]], ["Design", "Hosting"])

        # Logged work which hasn't been invoiced yet
        consulting = factories.ServiceFactory.create(
            project=project, effort_type="Consulting", effort_rate=200
        )
        hours = factories.LoggedHoursFactory.create(service=consulting, hours=3)
        response = create({"project": project.pk, "services": [consulting.pk]})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["total_excl_tax"], "600.00")
        hours.refresh_from_db()
        self.assertTrue(hours.invoice_service)

        # Sources of single services of the project, offer or logbook
        factories.LoggedHoursFactory.create(service=consulting, hours=1)
        response = create({
            "project": project.pk,
            "services": [consulting.pk],
            "sources": {consulting.pk: "surplus"},
        })
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["loc"][:4],
            ["body", "data", "sources", str(consulting.pk)],
        )
        other = factories.ServiceFactory.create()
        response = create({
            "project": project.pk,
            "services": [consulting.pk],
            "sources": {other.pk: "offer"},
            "disable_logging": [other.pk],
        })
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"] for error in response.json()["detail"]],
            [
                ["body", "data", "sources", str(other.pk)],
                ["body", "data", "disable_logging", 0],
            ],
        )
        # Services of the project which aren't invoiced aren't ignored silently
        not_invoiced = factories.ServiceFactory.create(project=project)
        response = create({
            "project": project.pk,
            "services": [consulting.pk],
            "disable_logging": [not_invoiced.pk],
        })
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"] for error in response.json()["detail"]],
            [["body", "data", "disable_logging", 0]],
        )
        response = create({
            "project": project.pk,
            "services": [consulting.pk],
            "sources": {consulting.pk: "logbook"},
            "disable_logging": [consulting.pk],
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["total_excl_tax"], "200.00")
        consulting.refresh_from_db()
        self.assertFalse(consulting.allow_logging)

        # Services invoices without offer need the services
        response = create({"project": project.pk, "type": "services"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["loc"], ["body", "data", "services"]
        )
        response = create({"project": project.pk, "subtotal": None})
        self.assertEqual(response.status_code, 422)

        # Invoices without project
        response = create({
            "contact": project.contact.pk,
            "subtotal": 300,
            "title": "Workshop",
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(Invoice.objects.get(pk=response.json()["id"]).project)
        response = create({"contact": project.contact.pk, "type": "credit"})
        self.assertEqual(response.status_code, 422)

        # Fields which don't apply to the type are errors, not ignored
        response = create({
            "project": project.pk,
            "type": "credit",
            "subtotal": 100,
            "discount": 10,
            "third_party_costs": 5,
        })
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"] for error in response.json()["detail"]],
            [["body", "data", "third_party_costs"], ["body", "data", "discount"]],
        )

        # Warnings are errors unless forced
        address = {"postal_address": "Short\nAddress"}
        response = create({"project": project.pk, "subtotal": 100} | address)
        self.assertEqual(response.status_code, 422)
        response = create(
            {"project": project.pk, "subtotal": 100} | address,
            "?ignore_warnings=short-postal-address",
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_pdf(self):
        """Invoices are downloaded as PDF like in the web interface"""
        invoice = factories.InvoiceFactory.create(
            title="Relaunch", postal_address="Anything\nStreet\nCity"
        )
        self.client.force_login(invoice.owned_by)
        response = self.client.get(f"/api/invoices/{invoice.pk}/pdf/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "application/pdf")
        self.assertIn("attachment", response["content-disposition"])
        self.assertTrue(b"".join(response).startswith(b"%PDF"))

    def test_create_draft_with_down_payments(self):
        """Final invoices deduct the down payments given"""
        project = factories.ProjectFactory.create()
        factories.PostalAddressFactory.create(person=project.contact)
        down_payment = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            type=Invoice.DOWN_PAYMENT,
            subtotal=1000,
            status=Invoice.SENT,
        )
        self.client.force_login(project.owned_by)

        def create(data):
            return self.client.post(
                "/api/invoices/",
                {"project": project.pk, "subtotal": 5000} | data,
                content_type="application/json",
            )

        response = create({"down_payments": [down_payment.pk + 1000]})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["loc"], ["body", "data", "down_payments"]
        )
        response = create({"down_payments": [down_payment.pk]})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["total_excl_tax"], "4000.00")
        down_payment.refresh_from_db()
        self.assertEqual(down_payment.down_payment_applied_to_id, response.json()["id"])

    def test_update_sent_invoice(self):
        """Sent invoices change through the invoice form: changing anything
        but the status, closing date, payment notice and third party costs
        is a warning, like in the web interface"""
        project = factories.ProjectFactory.create()
        invoice = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            status=Invoice.SENT,
            invoiced_on=in_days(-10),
            due_on=in_days(5),
            subtotal=1000,
            postal_address=ADDRESS,
        )
        other = factories.UserFactory.create(_short_name="zz")
        self.client.force_login(project.owned_by)
        url = f"/api/invoices/{invoice.code}/"

        def patch(data, query=""):
            return self.client.patch(url + query, data, content_type="application/json")

        response = patch({"owned_by": "zz", "title": "Handed over"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error.get("code") for error in response.json()["detail"]],
            ["maybe-unintentional-invoice-change"],
        )
        response = patch(
            {"owned_by": "zz", "title": "Handed over"},
            "?ignore_warnings=maybe-unintentional-invoice-change",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["owned_by"], "zz")
        invoice.refresh_from_db()
        self.assertEqual((invoice.owned_by, invoice.title), (other, "Handed over"))

        # Amounts warn too
        response = patch({"subtotal": "500.00"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["code"], "maybe-unintentional-invoice-change"
        )

        response = patch({"owned_by": "nobody"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["loc"], ["body", "data", "owned_by"]
        )

        # Settling it
        settle = {
            "status": "paid",
            "closed_on": in_days(-1).isoformat(),
            "payment_notice": "Bank transfer",
        }
        response = patch(settle, "?dry_run=true")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], "paid")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.SENT)

        response = patch(settle)
        self.assertEqual(response.status_code, 200, response.content)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.PAID)
        self.assertEqual(invoice.closed_on, in_days(-1))
        self.assertEqual(invoice.payment_notice, "Bank transfer")
        self.assertEqual(invoice.total_excl_tax, 1000)

    def test_update_status_sends_nothing(self):
        """Setting the status to sent records it, nothing is mailed"""
        invoice = factories.InvoiceFactory.create(
            due_on=in_days(15), postal_address=ADDRESS
        )
        self.client.force_login(invoice.owned_by)
        response = self.client.patch(
            f"/api/invoices/{invoice.pk}/",
            {"status": "sent"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.SENT)
        self.assertEqual(mail.outbox, [])

    def test_update_freeze_date(self):
        """The freeze date refuses invoice dates and changes like the form"""
        FreezeDate.objects.create(up_to=in_days(-10))
        draft = factories.InvoiceFactory.create(
            invoiced_on=in_days(-20), due_on=in_days(-5), postal_address=ADDRESS
        )
        self.client.force_login(draft.owned_by)

        def patch(invoice, data, query=""):
            return self.client.patch(
                f"/api/invoices/{invoice.pk}/{query}",
                data,
                content_type="application/json",
            )

        response = patch(draft, {"status": "sent"}, "?ignore_warnings=invoiced-in-past")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"],
            [
                {
                    "loc": ["body", "data", "invoiced_on"],
                    "msg": "Cannot create an invoice with a date of"
                    f" {local_date_format(in_days(-10))} or earlier anymore.",
                }
            ],
        )
        response = patch(
            draft,
            {
                "status": "sent",
                "invoiced_on": in_days(0).isoformat(),
                "due_on": in_days(15).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

        # Freezed invoices change only some fields
        freezed = factories.InvoiceFactory.create(
            status=Invoice.SENT,
            invoiced_on=in_days(-20),
            due_on=in_days(-5),
            subtotal=100,
            postal_address=ADDRESS,
        )
        response = patch(freezed, {"subtotal": "200.00", "due_on": None})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"] for error in response.json()["detail"]],
            [["body", "data", "due_on"], ["body", "data", "subtotal"]],
        )
        response = patch(freezed, {"status": "canceled", "payment_notice": "Twice"})
        self.assertEqual(response.status_code, 200, response.content)
        freezed.refresh_from_db()
        self.assertEqual(freezed.status, Invoice.CANCELED)

    def test_update_fields(self):
        """Invoices in preparation change most fields, those which don't
        apply to the type are refused"""
        project = factories.ProjectFactory.create()
        down_payment = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            type=Invoice.DOWN_PAYMENT,
            subtotal=1000,
            status=Invoice.SENT,
            postal_address=ADDRESS,
        )
        invoice = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            subtotal=5000,
            postal_address=ADDRESS,
        )
        credit = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            type=Invoice.CREDIT,
            subtotal=-100,
            postal_address=ADDRESS,
        )
        self.client.force_login(project.owned_by)

        def patch(invoice, data):
            return self.client.patch(
                f"/api/invoices/{invoice.pk}/", data, content_type="application/json"
            )

        response = patch(
            invoice,
            {
                "subtotal": "4000.00",
                "discount": "100.00",
                "liable_to_vat": False,
                "description": "Phase 1",
                "service_period_from": "2026-10-01",
                "service_period_until": "2026-10-31",
                "down_payments": [down_payment.pk],
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["total"], "2900.00")
        invoice.refresh_from_db()
        self.assertFalse(invoice.liable_to_vat)
        self.assertEqual(invoice.down_payment_total, 1000)

        response = patch(invoice, {"down_payments": []})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["total"], "3900.00")

        response = patch(invoice, {"tax_rate": 8.1, "liable_to_vat": True})
        self.assertEqual(response.status_code, 200, response.content)

        for data, field in [
            ({"customer": factories.OrganizationFactory.create().pk}, "customer"),
            ({"status": "maybe"}, "status"),
            ({"type": "credit"}, "type"),
        ]:
            with self.subTest(data=data):
                response = patch(invoice, data)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["detail"][0]["loc"][-1], field)

        response = patch(credit, {"discount": "10.00"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"],
            [
                {
                    "loc": ["body", "data", "discount"],
                    "msg": "This field cannot be changed.",
                }
            ],
        )
        response = patch(credit, {"subtotal": "150.00"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["total_excl_tax"], "-150.00")

        response = patch(invoice, {"status": "canceled"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["msg"],
            "Invoices which haven't been sent are deleted, not cancelled.",
        )

    def test_delete(self):
        """Invoices in preparation are deleted like in the web interface,
        the down payments and logged work they deducted are released"""
        project = factories.ProjectFactory.create()
        sent = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            type=Invoice.DOWN_PAYMENT,
            subtotal=1000,
            status=Invoice.SENT,
        )
        draft = factories.InvoiceFactory.create(
            project=project, customer=project.customer, subtotal=5000
        )
        sent.down_payment_applied_to = draft
        sent.save()
        self.client.force_login(project.owned_by)

        response = self.client.delete(f"/api/invoices/{sent.pk}/")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"],
            [
                {
                    "loc": ["path", "invoice_id"],
                    "msg": "Invoices in preparation may be deleted, others not.",
                }
            ],
        )

        url = f"/api/invoices/{draft.code}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error.get("code") for error in response.json()["detail"]],
            ["release-down-payments"],
        )
        response = self.client.delete(
            f"{url}?ignore_warnings=release-down-payments&dry_run=true"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["id"], draft.pk)
        self.assertTrue(Invoice.objects.filter(pk=draft.pk).exists())

        response = self.client.delete(f"{url}?ignore_warnings=release-down-payments")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["code"], draft.code)
        self.assertFalse(Invoice.objects.filter(pk=draft.pk).exists())
        sent.refresh_from_db()
        self.assertIsNone(sent.down_payment_applied_to)
