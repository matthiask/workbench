from datetime import date

from django.test import TestCase

from workbench import factories
from workbench.awt.models import Year
from workbench.awt.utils import monthly_days


class AWTTest(TestCase):
    def test_redirect(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)
        response = self.client.get("/report/annual-working-time/")
        self.assertRedirects(response, "/")
        self.assertEqual(Year.objects.current(), None)

        year = factories.YearFactory.create()
        response = self.client.get("/report/annual-working-time/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Year.objects.current(), year)

    def test_absences_list(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)
        response = self.client.get("/absences/")
        self.assertRedirects(response, "/absences/?u={}".format(user.pk))

    def test_year(self):
        year = factories.YearFactory.create()
        self.assertEqual(year.months, [30 for i in range(12)])

    def test_monthly_days(self):
        for from_, until_, dates in [
            (
                date(2018, 2, 1),
                date(2018, 7, 31),
                [
                    (date(2018, 2, 1), 28),
                    (date(2018, 3, 1), 31),
                    (date(2018, 4, 1), 30),
                    (date(2018, 5, 1), 31),
                    (date(2018, 6, 1), 30),
                    (date(2018, 7, 1), 31),
                ],
            ),
            (
                date(2018, 2, 2),
                date(2018, 7, 30),
                [
                    (date(2018, 2, 1), 27),
                    (date(2018, 3, 1), 31),
                    (date(2018, 4, 1), 30),
                    (date(2018, 5, 1), 31),
                    (date(2018, 6, 1), 30),
                    (date(2018, 7, 1), 30),
                ],
            ),
            (date(2018, 2, 10), date(2018, 2, 19), [(date(2018, 2, 1), 10)]),
        ]:
            with self.subTest(locals()):
                self.assertEqual(list(monthly_days(from_, until_)), dates)
