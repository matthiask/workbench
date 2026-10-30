import datetime as dt

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.invoices.models import Invoice
from workbench.notes.models import Note
from workbench.offers.models import Offer
from workbench.tools.validation import in_days, monday


class APIQueriesTest(TestCase):
    """The number of queries of list endpoints doesn't grow with the number
    of results, pages can have up to 10000 of them"""

    def tearDown(self):
        deactivate_all()

    def setUp(self):
        self.user = factories.UserFactory.create(_short_name="ab")
        self.client.force_login(self.user)

    def queries(self, url):
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        return len(context)

    def assert_constant(self, url, create):
        create()
        self.queries(url)  # Fills caches, e.g. of content types
        one = self.queries(url)
        for _i in range(5):
            create()
        self.assertEqual(self.queries(url), one, url)

    def test_searches(self):
        def project():
            return factories.ProjectFactory.create(owned_by=self.user)

        def offer():
            offer = factories.OfferFactory.create(project=project())
            factories.ServiceFactory.create(project=offer.project, offer=offer)
            return offer

        def invoice():
            p = project()
            return factories.InvoiceFactory.create(
                project=p,
                customer=p.customer,
                contact=p.contact,
                status=Invoice.SENT,
                invoiced_on=in_days(-60),
                due_on=in_days(-30),
            )

        def deal():
            deal = factories.DealFactory.create(owned_by=self.user)
            deal.values.create(type=self.value_type, value=100)
            deal.contributions.create(user=self.user)
            deal.related_offers.add(offer())
            return deal

        def note():
            return Note.objects.create(
                content_object=deal(),
                created_by=self.user,
                title="Call",
                description="Call",
            )

        def team():
            factories.TeamFactory.create().members.add(factories.UserFactory.create())

        self.value_type = factories.ValueTypeFactory.create()
        for url, create in [
            ("/api/projects/", project),
            ("/api/offers/", offer),
            ("/api/invoices/", invoice),
            ("/api/invoices/reminders/", invoice),
            ("/api/recurring-invoices/", factories.RecurringInvoiceFactory.create),
            (
                "/api/projected-invoices/",
                lambda: factories.ProjectedInvoiceFactory.create(project=project()),
            ),
            ("/api/deals/", deal),
            ("/api/notes/", note),
            (
                "/api/services/",
                lambda: factories.ServiceFactory.create(project=project()),
            ),
            (
                "/api/logbook/hours/",
                lambda: factories.LoggedHoursFactory.create(rendered_by=self.user),
            ),
            ("/api/logbook/costs/", factories.LoggedCostFactory.create),
            (
                "/api/absences/?since=2000-01-01",
                lambda: factories.AbsenceFactory.create(starts_on=in_days(5)),
            ),
            ("/api/users/", factories.UserFactory.create),
            ("/api/teams/", team),
            ("/api/contacts/organizations/", factories.OrganizationFactory.create),
            ("/api/contacts/people/", factories.PersonFactory.create),
        ]:
            with self.subTest(url=url):
                self.assert_constant(url, create)

    def test_reports(self):
        def logged():
            service = factories.ServiceFactory.create(
                project=factories.ProjectFactory.create(owned_by=self.user)
            )
            factories.LoggedHoursFactory.create(
                service=service, rendered_by=factories.UserFactory.create()
            )
            factories.LoggedCostFactory.create(service=service, third_party_costs=10)
            factories.ProjectedInvoiceFactory.create(
                project=service.project, invoiced_on=in_days(30), gross_margin=100
            )
            factories.InvoiceFactory.create(
                project=service.project,
                customer=service.project.customer,
                contact=service.project.contact,
                status=Invoice.SENT,
                invoiced_on=in_days(-10),
                due_on=in_days(20),
            )

        def deal():
            factories.DealFactory.create(
                status=factories.DealFactory._meta.model.ACCEPTED,
                closed_on=dt.date.today(),
                closing_type=self.closing_type,
            ).contributions.create(user=self.user)

        self.closing_type = factories.ClosingTypeFactory.create(title="Won")
        for url, create in [
            ("/api/reports/budget/", logged),
            ("/api/reports/projected-gross-margin/", logged),
            ("/api/reports/third-party-costs/", logged),
            ("/api/reports/open-items/", logged),
            ("/api/reports/hours-per-customer/", logged),
            ("/api/reports/hours-per-type/", logged),
            ("/api/reports/green-hours/", logged),
            ("/api/reports/planning-vs-logbook/", logged),
            ("/api/reports/logging/", logged),
            ("/api/reports/squeeze/?period=this-month", logged),
            ("/api/deals/stats/", deal),
            ("/api/deals/history/", deal),
            ("/api/planning/export/", self.planned_work),
        ]:
            with self.subTest(url=url):
                self.assert_constant(url, create)

    def planned_work(self):
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project, status=Offer.OFFERED)
        factories.PlannedWorkFactory.create(
            project=project,
            offer=offer,
            user=self.user,
            weeks=[in_days(0) - dt.timedelta(days=in_days(0).weekday())],
            milestone=factories.MilestoneFactory.create(
                project=project, date=in_days(3)
            ),
        )

    def test_details(self):
        """Details don't run a query per related object either"""
        self.value_type = factories.ValueTypeFactory.create()
        project = factories.ProjectFactory.create(owned_by=self.user)
        offer = factories.OfferFactory.create(project=project)
        invoice = factories.InvoiceFactory.create(
            project=project, customer=project.customer, contact=project.contact
        )
        deal = factories.DealFactory.create(owned_by=self.user)
        organization = factories.OrganizationFactory.create()
        person = factories.PersonFactory.create(organization=organization)

        def service():
            factories.ServiceFactory.create(project=project, offer=offer)

        def deal_related():
            deal.values.create(type=factories.ValueTypeFactory.create(), value=100)
            deal.contributions.create(user=factories.UserFactory.create())
            deal.related_offers.add(
                factories.OfferFactory.create(project=factories.ProjectFactory())
            )

        def person_related():
            factories.PersonFactory.create(organization=organization)
            person.emailaddresses.create(type="work", email="x@example.com")
            person.phonenumbers.create(type="work", phone_number="+41 44 000 00 00")
            factories.PostalAddressFactory.create(person=person)

        def planned_work():
            factories.PlannedWorkFactory.create(
                project=project,
                offer=offer,
                user=factories.UserFactory.create(),
                weeks=[monday()],
                milestone=factories.MilestoneFactory.create(
                    project=project, date=in_days(30)
                ),
            )
            factories.AbsenceFactory.create(starts_on=in_days(5))

        for url, create in [
            (f"/api/projects/{project.pk}/", service),
            (f"/api/offers/{offer.pk}/", service),
            (f"/api/projects/{project.pk}/offers/context/", service),
            (f"/api/projects/{project.pk}/planning/context/", planned_work),
            (f"/api/invoices/{invoice.pk}/", service),
            (f"/api/deals/{deal.pk}/", deal_related),
            (f"/api/contacts/organizations/{organization.pk}/", person_related),
            (f"/api/contacts/people/{person.pk}/", person_related),
        ]:
            with self.subTest(url=url):
                self.assert_constant(url, create)

    def test_overview(self):
        def actionable():
            project = factories.ProjectFactory.create(owned_by=self.user)
            factories.ServiceFactory.create(
                project=project,
                offer=factories.OfferFactory.create(
                    project=project, owned_by=self.user
                ),
            )
            factories.InvoiceFactory.create(
                project=project,
                customer=project.customer,
                contact=project.contact,
                owned_by=self.user,
            )
            deal = factories.DealFactory.create(owned_by=self.user)
            deal.values.create(type=self.value_type, value=100)
            deal.contributions.create(user=factories.UserFactory.create())
            deal.related_offers.add(factories.OfferFactory.create(project=project))
            factories.PlannedWorkFactory.create(
                project=project, user=self.user, weeks=[monday()]
            )

        self.value_type = factories.ValueTypeFactory.create()
        self.assert_constant("/api/me/overview/", actionable)
