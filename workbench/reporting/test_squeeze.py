from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.invoices.models import Invoice
from workbench.offers.models import Offer
from workbench.reporting.squeeze import (
    BASE_HOURLY_RATE,
    project_gross_margin,
    squeeze_data,
)
from workbench.tools.validation import in_days


class SqueezeTest(TestCase):
    def setUp(self):
        deactivate_all()

    def offer(self, project, *, status, hours):
        offer = factories.OfferFactory.create(project=project, status=status)
        service = factories.ServiceFactory.create(
            project=project,
            offer=offer,
            effort_type="Any",
            effort_rate=200,
            effort_hours=hours,
        )
        offer.save()  # Recalculate the total
        return service

    def test_offered_rate_only_uses_accepted_offers(self):
        """The rate based on accepted offers only uses their hours"""
        project = factories.ProjectFactory.create()
        self.offer(project, status=Offer.ACCEPTED, hours=10)
        self.offer(project, status=Offer.IN_PREPARATION, hours=10)

        pgm = project_gross_margin(project)
        self.assertEqual(pgm["offered_rate"], 200)
        self.assertEqual(pgm["hours"], 20)
        self.assertEqual(pgm["rate"], 100)

    def test_logged_hours_on_optional_services(self):
        """Hours logged on optional services are added on top"""
        project = factories.ProjectFactory.create()
        self.offer(project, status=Offer.ACCEPTED, hours=10)
        optional = factories.ServiceFactory.create(
            project=project, effort_hours=10, is_optional=True
        )
        factories.LoggedHoursFactory.create(service=optional, hours=5)

        self.assertEqual(project_gross_margin(project)["hours"], 15)

        data = squeeze_data((in_days(-1), in_days(1)))
        row = next(p for p in data["projects"] if p["project"] == project)
        self.assertEqual(row["hours"], 15)

    def test_closed_projects_only_count_logged_hours(self):
        """Squeeze and the project use logged hours only for closed projects"""
        project = factories.ProjectFactory.create()
        service = self.offer(project, status=Offer.ACCEPTED, hours=20)
        factories.LoggedHoursFactory.create(service=service, hours=10)
        project.closed_on = in_days(0)
        project.save()

        self.assertEqual(project_gross_margin(project)["hours"], 10)

        data = squeeze_data((in_days(-1), in_days(1)))
        row = next(p for p in data["projects"] if p["project"] == project)
        self.assertEqual(row["hours"], 10)

    def test_offered_rate_uses_logged_hours(self):
        """Hours logged beyond the accepted offers' hours lower their rate"""
        project = factories.ProjectFactory.create()
        service = self.offer(project, status=Offer.ACCEPTED, hours=10)
        factories.LoggedHoursFactory.create(service=service, hours=20)

        self.assertEqual(project_gross_margin(project)["offered_rate"], 100)

    def test_profitability_modal(self):
        """The profitability modal shows both rates"""
        project = factories.ProjectFactory.create()
        self.offer(project, status=Offer.ACCEPTED, hours=10)
        self.offer(project, status=Offer.IN_PREPARATION, hours=10)
        self.client.force_login(project.owned_by)

        response = self.client.get(project.urls["profitability"])
        self.assertContains(response, "100.00/h")
        self.assertContains(response, "200.00/h")

    def test_zero_rate_hours_get_a_share(self):
        """Hours on services with a rate of 0.00 are weighted with the base rate"""
        project = factories.ProjectFactory.create()
        service = self.offer(project, status=Offer.ACCEPTED, hours=10)
        package = factories.ServiceFactory.create(project=project, effort_rate=0)
        rated = factories.LoggedHoursFactory.create(service=service, hours=10)
        unrated = factories.LoggedHoursFactory.create(service=package, hours=10)

        data = squeeze_data((in_days(-1), in_days(1)))
        row = next(p for p in data["projects"] if p["project"] == project)
        rated_contrib = row["by_user"][rated.rendered_by]
        unrated_contrib = row["by_user"][unrated.rendered_by]
        self.assertAlmostEqual(
            unrated_contrib["gross_margin"] / rated_contrib["gross_margin"],
            BASE_HOURLY_RATE / 200,
        )
        self.assertEqual(unrated_contrib["hours_rate_unknown"], 10)

    def test_third_party_costs_are_not_subtracted_twice(self):
        """Logged third party costs invoiced with a fixed amount invoice count once"""
        project = factories.ProjectFactory.create()
        service = factories.ServiceFactory.create(project=project)
        factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            type=Invoice.FIXED,
            subtotal=1000,
            third_party_costs=600,
            status=Invoice.SENT,
            due_on=in_days(15),
        )
        cost = factories.LoggedCostFactory.create(
            service=service, cost=600, third_party_costs=600
        )
        factories.LoggedHoursFactory.create(service=service)

        self.assertEqual(project_gross_margin(project)["invoiced"], 400)
        data = squeeze_data((in_days(-1), in_days(1)))
        row = next(p for p in data["projects"] if p["project"] == project)
        self.assertEqual(row["invoiced"], 400)

        # Logged third party costs exceeding those on invoices are subtracted
        cost.third_party_costs = 800
        cost.save()
        self.assertEqual(project_gross_margin(project)["invoiced"], 200)
