from django.test import TestCase

from workbench.audit.models import LoggedAction
from workbench import factories


class FactoriesTestCase(TestCase):
    def test_factories(self):
        factories.ServiceFactory.create()
        factories.InvoiceFactory.create()

        types = factories.service_types()
        self.assertAlmostEqual(types.production.hourly_rate, 180)

        self.assertEqual(LoggedAction.objects.count(), 14)
