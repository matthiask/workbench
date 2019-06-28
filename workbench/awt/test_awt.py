from datetime import date
from decimal import Decimal

from django.test import TestCase

from workbench import factories
from workbench.awt.models import Absence, Employment, Year
from workbench.awt.reporting import annual_working_time
from workbench.awt.utils import monthly_days
from workbench.tools.formats import local_date_format
from workbench.tools.testing import messages


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

    def test_working_time(self):
        year = factories.YearFactory.create(year=2018)
        service = factories.ServiceFactory.create()
        user = service.project.owned_by
        user.loggedhours.create(
            service=service,
            created_by=user,
            hours=1000,
            description="anything",
            rendered_on=date(2018, 1, 1),
        )
        user.absences.create(starts_on=date(2018, 1, 1), days=5, is_vacation=True)
        user.absences.create(starts_on=date(2018, 4, 1), days=45, is_vacation=True)
        user.absences.create(starts_on=date(2018, 7, 1), days=10, is_vacation=False)
        user.absences.create(starts_on=date(2018, 10, 1), days=10, is_vacation=True)
        user.employments.create(
            date_from=date(2014, 1, 1),
            date_until=date(2014, 3, 31),
            percentage=80,
            vacation_weeks=5,
        )
        user.employments.create(
            date_from=date(2017, 1, 1), percentage=80, vacation_weeks=5
        )
        user.employments.create(
            date_from=date(2018, 10, 1), percentage=100, vacation_weeks=5
        )

        employments = list(user.employments.all())
        self.assertEqual(employments[0].date_until, date(2014, 3, 31))
        self.assertEqual(employments[1].date_until, date(2018, 9, 30))
        self.assertEqual(employments[2].date_until, date(9999, 12, 31))

        awt = annual_working_time(year, users=[user])[0]

        self.assertAlmostEqual(awt["totals"]["target_days"], Decimal("360"))
        self.assertAlmostEqual(awt["totals"]["percentage"], Decimal("85"))
        # 3/4 * 20 + 1/4 * 25 = 21.25
        self.assertAlmostEqual(
            awt["totals"]["available_vacation_days"], Decimal("21.25")
        )

        self.assertAlmostEqual(awt["totals"]["hours"], Decimal("1000"))
        self.assertAlmostEqual(awt["totals"]["vacation_days"], Decimal("60"))
        # 21.25 - 50 - 10 = -38.75
        self.assertAlmostEqual(
            awt["totals"]["vacation_days_correction"], Decimal("-38.75")
        )
        self.assertAlmostEqual(awt["totals"]["other_absences"], Decimal("10"))

        # 3/4 * 80% * 360 + 1/4 * 100% * 360 = 306
        self.assertAlmostEqual(awt["totals"]["target"], Decimal("-306"))

        # 1000 / 8 + 21.25 + 10 = 125 + 21.25 + 10 = 156.25
        self.assertAlmostEqual(awt["totals"]["working_time"], Decimal("156.25"))

        # 306 * 8 - 1000 - 21.25 * 8 - 10 * 8 = 1198
        self.assertAlmostEqual(awt["totals"]["running_sum"], Decimal("-1198"))

    def test_admin_list(self):
        self.client.force_login(factories.UserFactory.create(is_admin=True))
        factories.YearFactory.create()
        response = self.client.get("/admin/awt/year/")
        self.assertContains(response, '<td class="field-days">360,00</td>')

    def test_absence_editing(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)
        response = self.client.post(
            "/absences/create/",
            {
                "user": user.pk,
                "starts_on": local_date_format(date.today()),
                "days": 3,
                "description": "Sick",
                "is_vacation": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)
        absence = Absence.objects.get()

        response = self.client.get(
            absence.urls["update"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)

        Absence.objects.update(starts_on=date(2018, 1, 1))
        response = self.client.get(
            absence.urls["update"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Abwesenheiten vergangener Jahre sind für die Bearbeitung gesperrt.",
        )

    def test_employment_model(self):
        factories.UserFactory.create()  # Additional instance for active_users()

        year = factories.YearFactory.create()
        user = factories.UserFactory.create()

        employment = Employment.objects.create(
            user=user, percentage=100, vacation_weeks=5, date_from=date(2018, 1, 1)
        )
        self.assertEqual(employment.date_until, date.max)
        self.assertEqual(str(employment), "Seit 01.01.2018")

        self.assertEqual(list(year.active_users()), [user])

        employment.date_until = date(2018, 6, 30)
        employment.save()
        self.assertEqual(str(employment), "01.01.2018 - 30.06.2018")

        self.assertEqual(list(year.active_users()), [])

    def test_report_view(self):
        factories.YearFactory.create()
        user = factories.UserFactory.create()
        inactive = factories.UserFactory.create()
        Employment.objects.create(user=user, percentage=50, vacation_weeks=5)

        self.client.force_login(factories.UserFactory.create())

        url = "/report/annual-working-time/"
        response = self.client.get(url)
        self.assertNotContains(response, str(user))
        self.assertNotContains(response, str(inactive))

        response = self.client.get(url + "?user=active")
        self.assertContains(response, str(user))
        self.assertNotContains(response, str(inactive))

        response = self.client.get(url + "?user=" + str(inactive.pk))
        self.assertContains(response, str(inactive))

        response = self.client.get(url + "?year=2018")
        self.assertRedirects(response, "/")
        self.assertEqual(messages(response), ["Sollzeit für 2018 nicht gefunden."])

    def test_non_ajax_redirect(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)
        absence = Absence.objects.create(user=user, starts_on=date.today(), days=1)
        response = self.client.get(absence.urls["detail"])
        self.assertRedirects(response, "/absences/?u=" + str(user.pk))
