from django.test import TestCase

from workbench import factories


class FactoriesTestCase(TestCase):
    def test_factories(self):
        factories.ServiceFactory.create()
        factories.InvoiceFactory.create()

        types = factories.service_types()
        self.assertAlmostEqual(types.production.billing_per_hour, 180)
