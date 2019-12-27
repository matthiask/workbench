import datetime as dt
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from workbench import factories
from workbench.awt.models import Absence, Employment
from workbench.awt.reporting import active_users, annual_working_time
from workbench.awt.utils import monthly_days
from workbench.tools.testing import messages


class AWTTest(TestCase):
    def test_redirect(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)
        response = self.client.get("/report/annual-working-time/?year=asdf")
        self.assertRedirects(response, "/report/annual-working-time/")

    def test_absences_list(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)
        response = self.client.get("/absences/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/absences/?user=0")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/absences/?user=-1")
        self.assertEqual(response.status_code, 200)

    def test_year(self):
        year = factories.YearFactory.create()
        self.assertEqual(year.months, [30 for i in range(12)])

    def test_monthly_days(self):
        for from_, until_, dates in [
            (
                dt.date(2018, 2, 1),
                dt.date(2018, 7, 31),
                [
                    (dt.date(2018, 2, 1), 28),
                    (dt.date(2018, 3, 1), 31),
                    (dt.date(2018, 4, 1), 30),
                    (dt.date(2018, 5, 1), 31),
                    (dt.date(2018, 6, 1), 30),
                    (dt.date(2018, 7, 1), 31),
                ],
            ),
            (
                dt.date(2018, 2, 2),
                dt.date(2018, 7, 30),
                [
                    (dt.date(2018, 2, 1), 27),
                    (dt.date(2018, 3, 1), 31),
                    (dt.date(2018, 4, 1), 30),
                    (dt.date(2018, 5, 1), 31),
                    (dt.date(2018, 6, 1), 30),
                    (dt.date(2018, 7, 1), 30),
                ],
            ),
            (dt.date(2018, 2, 10), dt.date(2018, 2, 19), [(dt.date(2018, 2, 1), 10)]),
        ]:
            with self.subTest(locals()):
                self.assertEqual(list(monthly_days(from_, until_)), dates)

    def test_working_time(self):
        service = factories.ServiceFactory.create()
        user = service.project.owned_by
        year = factories.YearFactory.create(
            year=2018, working_time_model=user.working_time_model
        )
        user.loggedhours.create(
            service=service,
            created_by=user,
            hours=1000,
            description="anything",
            rendered_on=dt.date(2018, 1, 1),
        )
        user.absences.create(starts_on=dt.date(2018, 1, 1), days=5, is_vacation=True)
        user.absences.create(starts_on=dt.date(2018, 4, 1), days=45, is_vacation=True)
        user.absences.create(starts_on=dt.date(2018, 7, 1), days=10, is_vacation=False)
        user.absences.create(starts_on=dt.date(2018, 10, 1), days=10, is_vacation=True)
        user.employments.create(
            date_from=dt.date(2014, 1, 1),
            date_until=dt.date(2014, 3, 31),
            percentage=80,
            vacation_weeks=5,
        )
        user.employments.create(
            date_from=dt.date(2017, 1, 1), percentage=80, vacation_weeks=5
        )
        user.employments.create(
            date_from=dt.date(2018, 10, 1), percentage=100, vacation_weeks=5
        )

        employments = list(user.employments.all())
        self.assertEqual(employments[0].date_until, dt.date(2014, 3, 31))
        self.assertEqual(employments[1].date_until, dt.date(2018, 9, 30))
        self.assertEqual(employments[2].date_until, dt.date(9999, 12, 31))

        awt = annual_working_time(year.year, users=[user])["statistics"][0]

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
        self.assertAlmostEqual(awt["totals"]["target"], Decimal("306") * 8)

        # 1000 / 8 + 21.25 + 10 = 125 + 21.25 + 10 = 156.25
        self.assertAlmostEqual(awt["totals"]["working_time"], Decimal("156.25") * 8)

        # 306 * 8 - 1000 - 21.25 * 8 - 10 * 8 = 1198
        self.assertAlmostEqual(awt["totals"]["running_sum"], Decimal("-1198"))

    def test_admin_list(self):
        self.client.force_login(factories.UserFactory.create(is_admin=True))
        factories.YearFactory.create()
        response = self.client.get("/admin/awt/year/")
        self.assertContains(response, '<td class="field-days">360.00</td>')

    def test_absence_editing(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)
        response = self.client.post(
            "/absences/create/",
            {
                "modal-user": user.pk,
                "modal-starts_on": dt.date.today().isoformat(),
                "modal-days": 3,
                "modal-description": "Sick",
                "modal-is_vacation": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)
        absence = Absence.objects.get()

        response = self.client.get(
            absence.urls["update"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)

        Absence.objects.update(starts_on=dt.date(2018, 1, 1))
        response = self.client.get(
            absence.urls["update"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Absences of past years are locked.")

    def test_only_this_year(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)
        response = self.client.post(
            "/absences/create/",
            {
                "modal-user": user.pk,
                "modal-starts_on": "2018-01-01",
                "modal-days": 3,
                "modal-description": "Sick",
                "modal-is_vacation": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(
            response, "Creating absences for past years is not allowed."
        )

    def test_employment_model(self):
        factories.UserFactory.create()  # Additional instance for active_users()

        year = factories.YearFactory.create()
        user = factories.UserFactory.create()

        employment = Employment.objects.create(
            user=user, percentage=100, vacation_weeks=5, date_from=dt.date(2018, 1, 1)
        )
        self.assertEqual(employment.date_until, dt.date.max)
        self.assertEqual(str(employment), "since 01.01.2018")

        self.assertEqual(list(active_users(year.year)), [user])

        employment.date_until = dt.date(2018, 6, 30)
        employment.save()
        self.assertEqual(str(employment), "01.01.2018 - 30.06.2018")

        self.assertEqual(list(active_users(year.year)), [])

    def test_report_view(self):
        year = factories.YearFactory.create()
        user = factories.UserFactory.create(
            _full_name="Fritz", working_time_model=year.working_time_model
        )
        inactive = factories.UserFactory.create(
            working_time_model=year.working_time_model
        )
        Employment.objects.create(user=user, percentage=50, vacation_weeks=5)

        # New user has a different working time model...
        self.client.force_login(factories.UserFactory.create(_full_name="Hans"))

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
        self.assertEqual(
            messages(response),
            [
                "No annual working time defined for user Hans"
                " with working time model Test."
            ],
        )

    def test_non_ajax_redirect(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)
        absence = Absence.objects.create(user=user, starts_on=dt.date.today(), days=1)
        response = self.client.get(absence.urls["detail"])
        self.assertRedirects(response, "/absences/?u=" + str(user.pk))

    def test_list(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)

        def code(suffix, status_code=200):
            self.assertEqual(
                self.client.get("/absences/?{}".format(suffix)).status_code, status_code
            )

        code("")
        code("u=-1")
        code("u={}".format(user.pk))

    def test_employment_validation(self):
        user = factories.UserFactory.create()
        kw = {"user": user, "percentage": 100, "vacation_weeks": 5, "notes": ""}
        Employment(**kw).full_clean()
        Employment(
            **kw, green_hours_target=20, hourly_labor_costs=Decimal(20)
        ).full_clean()

        msg = [
            (
                "__all__",
                [
                    "Either provide both hourly labor costs"
                    " and green hours target or none."
                ],
            )
        ]

        with self.assertRaises(ValidationError) as cm:
            Employment(**kw, green_hours_target=20).full_clean()
        self.assertEqual(list(cm.exception), msg)

        with self.assertRaises(ValidationError) as cm:
            Employment(**kw, hourly_labor_costs=20).full_clean()
        self.assertEqual(list(cm.exception), msg)
