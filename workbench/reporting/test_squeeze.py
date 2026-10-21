from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.offers.models import Offer
from workbench.reporting.squeeze import project_gross_margin, squeeze_data
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
