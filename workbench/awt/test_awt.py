import datetime as dt
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test.utils import override_settings
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts.features import FEATURES
from workbench.awt.models import Absence, Employment
from workbench.awt.reporting import active_users, annual_working_time
from workbench.awt.utils import monthly_days
from workbench.tools.forms import WarningsForm
from workbench.tools.testing import check_code, messages
from workbench.tools.validation import in_days


class AWTTest(TestCase):
    def setUp(self):
        deactivate_all()

    def test_redirect(self):
        """Invalid year produces a redirect"""
        user = factories.UserFactory.create()
        self.client.force_login(user)
        response = self.client.get("/report/annual-working-time/?year=asdf")
        self.assertRedirects(response, "/report/annual-working-time/")

    def test_year(self):
        """Basic year methods work"""
        year = factories.YearFactory.create()
        self.assertEqual(year.months, [30 for i in range(12)])

    def test_monthly_days(self):
        """Days per month are calculated correctly  for partial months"""
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
        """Verify that the annual working time report yields correct results"""
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
        user.absences.create(starts_on=dt.date(2018, 1, 1), days=5, reason="vacation")
        user.absences.create(starts_on=dt.date(2018, 4, 1), days=45, reason="vacation")
        user.absences.create(starts_on=dt.date(2018, 7, 1), days=10, reason="paid")
        user.absences.create(starts_on=dt.date(2018, 10, 1), days=10, reason="vacation")
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

        # Should have no effect
        a = user.absences.create(starts_on=dt.date(2018, 8, 1), days=10, reason="other")
        self.assertFalse(a.is_working_time)

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
        self.assertAlmostEqual(awt["totals"]["absence_vacation"], Decimal("60"))
        # 21.25 - 50 - 10 = -38.75
        self.assertAlmostEqual(
            awt["totals"]["vacation_days_correction"], Decimal("-38.75")
        )
        self.assertAlmostEqual(awt["totals"]["absence_sickness"], Decimal("0"))
        self.assertAlmostEqual(awt["totals"]["absence_paid"], Decimal("10"))

        # 3/4 * 80% * 360 + 1/4 * 100% * 360 = 306
        self.assertAlmostEqual(awt["totals"]["target"], Decimal("306") * 8)

        # 1000 / 8 + 21.25 + 10 = 125 + 21.25 + 10 = 156.25
        self.assertAlmostEqual(awt["totals"]["working_time"], Decimal("156.25") * 8)

        # 306 * 8 - 1000 - 21.25 * 8 - 10 * 8 = 1198
        self.assertAlmostEqual(awt["totals"]["running_sum"], Decimal("-1198"))

        # Now, test that the PDF does not crash
        self.client.force_login(user)

        response = self.client.get("/report/annual-working-time/?export=pdf&year=2018")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "application/pdf")

        user.employments.all().delete()
        response = self.client.get("/report/annual-working-time/?export=pdf&year=2018")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "application/pdf")

        user.absences.create(
            starts_on=dt.date(2018, 10, 1), days=10, reason="correction"
        )
        response = self.client.get("/report/annual-working-time/?export=pdf&year=2018")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "application/pdf")

    def test_admin_list(self):
        """The admin changelist of years contains the calculated sum of working days"""
        self.client.force_login(factories.UserFactory.create(is_admin=True))
        factories.YearFactory.create()
        response = self.client.get("/admin/awt/year/")
        self.assertContains(response, '<td class="field-days">360.00</td>')

    def test_absence_editing(self):
        """Creating and updating absences in the current year works"""
        user = factories.UserFactory.create()
        self.client.force_login(user)
        response = self.client.post(
            "/absences/create/",
            {
                "modal-user": user.pk,
                "modal-starts_on": dt.date.today().isoformat(),
                "modal-days": 3,
                "modal-description": "Sick",
                "modal-reason": "sickness",
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

        response = self.client.post(
            "/absences/create/",
            {
                "modal-user": user.pk,
                "modal-starts_on": "2018-01-01",
                "modal-days": 3,
                "modal-description": "Sick",
                "modal-reason": "sickness",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(
            response, "Creating absences for past years is not allowed."
        )

    def test_no_data_no_crash(self):
        """POSTing the absence form without any data does not crash the backend"""
        user = factories.UserFactory.create()
        self.client.force_login(user)
        response = self.client.post(
            "/absences/create/", {}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)

    def test_planning_skills(self):
        """Creating absences in the far future requires impressive-planning-skills"""
        user = factories.UserFactory.create()
        self.client.force_login(user)
        response = self.client.post(
            "/absences/create/",
            {
                "modal-user": user.pk,
                "modal-starts_on": "2100-01-01",
                "modal-days": 3,
                "modal-description": "Sick",
                "modal-reason": "sickness",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(
            response,
            "Impressive planning skills or wrong date?"
            " Absence starts in more than one year.",
        )

        response = self.client.post(
            "/absences/create/",
            {
                "modal-user": user.pk,
                "modal-starts_on": "2100-01-01",
                "modal-days": 3,
                "modal-description": "Sick",
                "modal-reason": "sickness",
                WarningsForm.ignore_warnings_id: "impressive-planning-skills",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

    def test_employment_model(self):
        """Exercise the employment model"""
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
        """The export view produces individual PDFs or ZIP files containing PDFs"""
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

        other = factories.UserFactory.create(working_time_model=year.working_time_model)
        Employment.objects.create(user=other, percentage=50, vacation_weeks=5)
        factories.AbsenceFactory.create(user=other)

        response = self.client.get(url + "?export=pdf&user=active")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "application/zip")

        response = self.client.get(url + "?export=pdf&user={}".format(user.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "application/pdf")

    def test_non_ajax_redirect(self):
        """The absence URL redirects when encountering a non-AJAX request"""
        absence = factories.AbsenceFactory.create()
        self.client.force_login(absence.user)
        response = self.client.get(absence.urls["detail"])
        self.assertRedirects(response, "/absences/?u=" + str(absence.user.pk))

    def test_list(self):
        """The absence list and its filters do not crash"""
        user = factories.UserFactory.create()
        self.client.force_login(user)

        code = check_code(self, "/absences/")
        code("")
        code("u=-1")
        code("u={}".format(user.pk))
        code("reason=sickness")
        code("reason=nothing", 302)
        code("export=xlsx")

    def test_employment_validation(self):
        """Test model validation of employments"""
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

        msg = [("date_until", ["Employments cannot end before they began."])]

        with self.assertRaises(ValidationError) as cm:
            Employment(
                **kw, date_from=dt.date.today(), date_until=dt.date(2020, 1, 30)
            ).full_clean()
        self.assertEqual(list(cm.exception), msg)

    def test_calendar(self):
        """The absence calendar report does not crash"""
        user = factories.UserFactory.create()
        self.client.force_login(user)

        Absence.objects.create(
            user=user,
            starts_on=dt.date.today(),
            days=0,
            description="Test",
            reason=Absence.VACATION,
        )
        Absence.objects.create(
            user=user,
            starts_on=in_days(10),
            ends_on=in_days(20),
            days=0,
            description="Test",
            reason=Absence.VACATION,
        )

        code = check_code(self, "/report/absence-calendar/")
        code("")

        team = factories.TeamFactory.create()
        user.teams.add(team)
        code("team={}".format(team.pk))
        code("team=abc", status_code=302)

    def test_absence_validation(self):
        """Test model validation of absences"""
        user = factories.UserFactory.create()
        kw = {
            "user": user,
            "starts_on": dt.date(2020, 2, 1),
            "days": 0,
            "description": "Nothing",
            "reason": "vacation",
        }
        Absence(**kw).full_clean()
        Absence(**kw, ends_on=dt.date(2020, 2, 2)).full_clean()

        msg = [("ends_on", ["Absences cannot end before they began."])]

        with self.assertRaises(ValidationError) as cm:
            Absence(**kw, ends_on=dt.date(2020, 1, 30)).full_clean()
        self.assertEqual(list(cm.exception), msg)

        msg = [("ends_on", ["Start and end must be in the same year."])]

        with self.assertRaises(ValidationError) as cm:
            Absence(**kw, ends_on=dt.date(2022, 1, 30)).full_clean()
        self.assertEqual(list(cm.exception), msg)

    @override_settings(FEATURES={FEATURES.WORKING_TIME_CORRECTION: False})
    def test_correction(self):
        """Absences with reason "correction" only with bookkeeping"""
        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.get(
            Absence.urls["create"],
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertNotContains(response, 'value="correction"')

        absence = factories.AbsenceFactory.create(user=user, reason=Absence.CORRECTION)
        response = self.client.get(
            absence.urls["update"],
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "You are not permitted to edit absences of type")

    def test_absences_without_enforce_same_week_logging(self):
        """Absences in past years without enforce_same_week_logging"""
        user = factories.UserFactory.create(enforce_same_week_logging=False)
        self.client.force_login(user)
        response = self.client.post(
            "/absences/create/",
            {
                "modal-user": user.pk,
                "modal-starts_on": dt.date(2020, 1, 1).isoformat(),
                "modal-days": 3,
                "modal-description": "Sick",
                "modal-reason": "sickness",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "past-years-absences")

        response = self.client.post(
            "/absences/create/",
            {
                "modal-user": user.pk,
                "modal-starts_on": dt.date(2020, 1, 1).isoformat(),
                "modal-days": 3,
                "modal-description": "Sick",
                "modal-reason": "sickness",
                WarningsForm.ignore_warnings_id: "past-years-absences",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

        absence = Absence.objects.get()
        response = self.client.get(
            absence.urls["update"],
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "<input")
