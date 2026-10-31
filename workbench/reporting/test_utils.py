from django.test import TestCase
from django.utils.translation import deactivate_all
from time_machine import travel

from workbench.reporting.utils import date_ranges


class UtilsTest(TestCase):
    @travel("2020-02-25 12:00")
    def test_date_ranges(self):
        """The date ranges utility returns expected values"""
        deactivate_all()
        self.assertEqual(
            date_ranges(),
            [
                ("2020-02-24", "2020-03-01", "this week"),
                ("2020-02-17", "2020-02-23", "last week"),
                ("2020-02-01", "2020-02-29", "this month"),
                ("2020-01-01", "2020-01-31", "last month"),
                ("2020-01-01", "2020-03-31", "this quarter"),
                ("2019-10-01", "2019-12-31", "last quarter"),
                ("2020-01-01", "2020-12-31", "this year"),
                ("2019-01-01", "2019-12-31", "last year"),
            ],
        )

    def test_accepted_offers_with_budget_retainer(self):
        """Budget retainer offers and other accepted offers aren't added up,
        the larger of both counts"""
        from workbench import factories
        from workbench.offers.models import Offer
        from workbench.reporting.project_budget_statistics import (
            project_budget_statistics,
        )
        from workbench.reporting.squeeze import gross_margin_components
        from workbench.reporting.utils import accepted_offers_by_project

        project = factories.ProjectFactory.create()

        def offer(total, *, retainer, third_party_costs=None):
            offer = factories.OfferFactory.create(
                project=project, status=Offer.ACCEPTED, is_budget_retainer=retainer
            )
            factories.ServiceFactory.create(
                project=project,
                offer=offer,
                cost=total,
                third_party_costs=third_party_costs,
            )
            offer.save()
            return offer

        offer(1000, retainer=True, third_party_costs=100)
        # Services without an offer use up the retained budget
        factories.ServiceFactory.create(project=project, cost=400)
        regular = offer(300, retainer=False, third_party_costs=50)

        self.assertEqual(
            accepted_offers_by_project([project.id])[project.id],
            {"total": 1000, "third_party_costs": 100},
        )
        self.assertEqual(
            gross_margin_components([project.id])[project.id]["offered"], 900
        )
        [row] = project_budget_statistics([project])["statistics"]
        self.assertEqual(row["sold"], 1000)

        # Other accepted offers add up to more than the retainer
        offer(800, retainer=False)
        self.assertEqual(
            accepted_offers_by_project([project.id])[project.id],
            {"total": 1100, "third_party_costs": 50},
        )
        regular.delete()
        self.assertEqual(
            accepted_offers_by_project([project.id])[project.id]["total"], 1000
        )
        self.assertEqual(accepted_offers_by_project([])[project.id]["total"], 0)
