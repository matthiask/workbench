from datetime import date

from django.test import TestCase

from workbench import factories
from workbench.accruals.models import Accrual, CutoffDate
from workbench.tools.testing import messages


class AccrualsTest(TestCase):
    def test_cutoff_days(self):
        self.client.force_login(factories.UserFactory.create())
        response = self.client.post("/accruals/create/", {"day": "01.01.2019"})
        day = CutoffDate.objects.get()
        self.assertRedirects(response, day.urls["detail"])
        response = self.client.post(day.urls["delete"])
        self.assertRedirects(response, day.urls["list"])
        self.assertEqual(
            messages(response), ["Stichtag '01.01.2019' wurde erfolgreich gelöscht."]
        )

    def test_cutoff_day_warning(self):
        self.client.force_login(factories.UserFactory.create())
        response = self.client.post("/accruals/create/", {"day": "31.01.2019"})
        self.assertContains(
            response, "Ungewöhnlicher Stichtag (nicht erster Tag des Monats)."
        )

    def test_cutoff_days_with_accruals(self):
        factories.InvoiceFactory.create(
            project=factories.ProjectFactory.create(),
            type=factories.Invoice.DOWN_PAYMENT,
            invoiced_on=date(2018, 12, 1),
            status=factories.Invoice.SENT,
            subtotal=100,
        )

        self.client.force_login(factories.UserFactory.create())
        response = self.client.post("/accruals/create/", {"day": "01.01.2019"})
        day = CutoffDate.objects.get()
        self.assertRedirects(response, day.urls["detail"])
        response = self.client.get(day.urls["detail"] + "?create_accruals=1")
        self.assertRedirects(response, day.urls["detail"])
        self.assertEqual(messages(response), ["Abgrenzungen erstellt."])

        self.assertEqual(Accrual.objects.count(), 1)

        response = self.client.post(day.urls["delete"])
        self.assertRedirects(response, day.urls["detail"])
        self.assertEqual(
            messages(response),
            ["Kann Stichtag mit schon existierenden Abgrenzungen nicht bearbeiten."],
        )

        response = self.client.get(day.urls["detail"] + "?xlsx=1")
        self.assertEqual(response.status_code, 200)
