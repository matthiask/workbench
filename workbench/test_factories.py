from django.test import TestCase

from workbench import factories
from workbench.audit.models import LoggedAction


class FactoriesTestCase(TestCase):
    def test_factories(self):
        factories.ServiceFactory.create()
        factories.InvoiceFactory.create()

        types = factories.service_types()
        self.assertAlmostEqual(types.production.hourly_rate, 180)

        # The exact count does not matter
        self.assertEqual(LoggedAction.objects.count(), 18)
