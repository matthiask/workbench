import datetime as dt

from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.deals.models import Deal
from workbench.invoices.models import Invoice
from workbench.offers.models import Offer
from workbench.projects.models import InternalType, Project
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

    def test_third_party_costs_of_optional_services(self):
        """Optional services aren't in the offer total, nor their costs"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        factories.ServiceFactory.create(
            project=project, offer=offer, cost=1000, third_party_costs=500
        )
        factories.ServiceFactory.create(
            project=project,
            offer=offer,
            cost=10000,
            third_party_costs=8000,
            is_optional=True,
        )
        offer.status = Offer.ACCEPTED
        offer.save()

        self.assertEqual(project_gross_margin(project)["offered"], 500)

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

    def test_hours_for_invoicing_split_the_gross_margin(self):
        """The gross margin is split by the value of the work, the project's
        share of the period and the rates use the time spent"""
        project = factories.ProjectFactory.create()
        service = self.offer(project, status=Offer.ACCEPTED, hours=40)
        fast = factories.LoggedHoursFactory.create(
            service=service, hours=10, hours_for_invoicing=20
        )
        slow = factories.LoggedHoursFactory.create(service=service, hours=10)

        data = squeeze_data((in_days(-1), in_days(1)))
        row = next(p for p in data["projects"] if p["project"] == project)
        self.assertEqual(row["hours_in_range"], 20)
        self.assertEqual(row["hours_for_invoicing_in_range"], 30)
        self.assertAlmostEqual(row["gross_margin_in_range"], 4000)  # 20/40 × 8000

        fast_contrib = row["by_user"][fast.rendered_by]
        slow_contrib = row["by_user"][slow.rendered_by]
        self.assertEqual(fast_contrib["hours"], 10)
        self.assertEqual(fast_contrib["hours_for_invoicing"], 20)
        self.assertAlmostEqual(float(fast_contrib["gross_margin"]), 4000 * 2 / 3)
        self.assertAlmostEqual(float(slow_contrib["gross_margin"]), 4000 / 3)
        self.assertAlmostEqual(float(fast_contrib["rate"]), 4000 * 2 / 3 / 10)

        user = next(u for u in data["users"] if u["user"] == fast.rendered_by)
        self.assertEqual(user["hours_for_invoicing_in_range"], 20)

        self.client.force_login(fast.rendered_by)
        url = f"/report/squeeze/?date_from={in_days(-1)}&date_until={in_days(1)}"
        self.assertContains(self.client.get(url), "Hours for invoicing")
        self.assertEqual(self.client.get(f"{url}&export=xlsx").status_code, 200)

    def test_work_worth_nothing_still_gets_the_share_of_the_period(self):
        """Without any value of the work in the period, the share of the
        period is split by hours"""
        project = factories.ProjectFactory.create()
        service = self.offer(project, status=Offer.ACCEPTED, hours=10)
        factories.LoggedHoursFactory.create(
            service=service, hours=5, rendered_on=in_days(-30)
        )
        factories.LoggedHoursFactory.create(
            service=service, hours=5, hours_for_invoicing=0
        )

        data = squeeze_data((in_days(-1), in_days(1)))
        row = next(p for p in data["projects"] if p["project"] == project)
        self.assertAlmostEqual(row["gross_margin_in_range"], 1000)  # 5/10 × 2000

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

    def test_expected_gross_margin_of_partial_months(self):
        """Periods may start in the middle of a month: The employment counts
        with its percentage and absences only with their days in the period"""
        user = factories.UserFactory.create()
        factories.EmploymentFactory.create(
            user=user, date_from=dt.date(2020, 1, 1), percentage=80
        )
        # Three days, two of them in the period
        factories.AbsenceFactory.create(
            user=user,
            starts_on=dt.date(2026, 10, 14),
            ends_on=dt.date(2026, 10, 16),
            days=3,
        )
        factories.AbsenceFactory.create(
            user=user, starts_on=dt.date(2026, 11, 2), ends_on=None, days=1
        )
        factories.LoggedHoursFactory.create(
            rendered_by=user, rendered_on=dt.date(2026, 10, 20)
        )

        data = squeeze_data((dt.date(2026, 10, 15), dt.date(2026, 11, 14)))
        (row,) = data["users"]
        self.assertAlmostEqual(row["employment_percentage"], 80)
        self.assertAlmostEqual(row["absence_days"], 3)

        # No absences, no absence days
        data = squeeze_data((dt.date(2026, 10, 18), dt.date(2026, 10, 31)))
        (row,) = data["users"]
        self.assertAlmostEqual(row["absence_days"], 0)

    def test_third_party_costs_of_down_payments(self):
        """Final invoices repeat the third party costs of down payments,
        down payments of recurring invoices may be the only ones"""
        project = factories.ProjectFactory.create()

        def invoice(type, third_party_costs):
            factories.InvoiceFactory.create(
                project=project,
                customer=project.customer,
                contact=project.contact,
                type=type,
                subtotal=1000,
                third_party_costs=third_party_costs,
                status=Invoice.SENT,
                due_on=in_days(15),
            )

        invoice(Invoice.DOWN_PAYMENT, 600)
        self.assertEqual(project_gross_margin(project)["invoiced"], 400)

        invoice(Invoice.FIXED, 600)
        self.assertEqual(project_gross_margin(project)["invoiced"], 1400)

    def test_unknown_specialist_field(self):
        """People without a specialist field are grouped in the language of
        the request"""
        factories.LoggedHoursFactory.create()
        data = squeeze_data((in_days(-1), in_days(1)))
        self.assertEqual([f["name"] for f in data["fields"]], ["<unknown>"])

    def test_outreach(self):
        """Hours spent on outreach compared with the contributions to
        accepted deals"""
        InternalType.objects.create(name="Other", percentage=10)
        outreach = InternalType.objects.create(
            name="Outreach", percentage=10, is_outreach=True
        )
        user = factories.UserFactory.create()
        project = factories.ProjectFactory.create(
            type=Project.INTERNAL, internal_type=outreach
        )
        factories.LoggedHoursFactory.create(
            service=factories.ServiceFactory.create(project=project),
            rendered_by=user,
            hours=4,
        )
        # Not outreach
        factories.LoggedHoursFactory.create(rendered_by=user, hours=3)

        deal = factories.DealFactory.create(
            owned_by=user, status=Deal.ACCEPTED, closed_on=dt.date.today()
        )
        deal.values.create(type=factories.ValueTypeFactory.create(), value=1000)
        deal.save()
        other = factories.UserFactory.create()
        deal.contributions.create(user=user, weight=60)
        deal.contributions.create(user=other, weight=40)
        # More deals, but less per hour
        third = factories.UserFactory.create()
        factories.LoggedHoursFactory.create(
            service=factories.ServiceFactory.create(project=project),
            rendered_by=third,
            hours=10,
        )
        third_deal = factories.DealFactory.create(
            owned_by=third, status=Deal.ACCEPTED, closed_on=dt.date.today()
        )
        third_deal.values.create(type=factories.ValueTypeFactory.create(), value=1000)
        third_deal.save()
        third_deal.contributions.create(user=third, weight=100)

        result = squeeze_data((in_days(-1), in_days(1)))["outreach"]
        self.assertEqual(result["internal_types"], [outreach])
        self.assertEqual(
            [
                (row["user"], row["hours"], row["deals"], row["deals_per_hour"])
                for row in result["users"]
            ],
            [(user, 4, 600, 150), (third, 10, 1000, 100), (other, 0, 400, None)],
        )
        [row, *_rest] = result["users"]
        self.assertEqual(row["by_project"], {project: 4})
        self.assertEqual(row["by_deal"], {deal: 600})
        self.assertEqual(result["totals"]["hours"], 14)
        self.assertEqual(result["totals"]["deals"], 2000)
        self.assertAlmostEqual(float(result["totals"]["deals_per_hour"]), 2000 / 14)

        self.client.force_login(user)
        url = f"/report/squeeze/?date_from={in_days(-1)}&date_until={in_days(1)}"
        response = self.client.get(url)
        self.assertContains(response, "Outreach hours")
        self.assertContains(response, 'data-bs-target="#outreach-help"')
        self.assertContains(response, "Accepted deals divided by outreach hours.")
        self.assertContains(response, f'id="outreach-user-{user.pk}"')
        self.assertContains(response, deal.get_absolute_url())
        self.assertEqual(self.client.get(f"{url}&export=xlsx").status_code, 200)
