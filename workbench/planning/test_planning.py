import datetime as dt
from decimal import Decimal

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.planning import reporting
from workbench.planning.forms import PlannedWorkSearchForm, PlanningRequestSearchForm
from workbench.planning.models import PlannedWork, PlanningRequest
from workbench.templatetags.workbench import link_or_none
from workbench.tools.validation import monday


class PlanningTest(TestCase):
    def setUp(self):
        deactivate_all()

    def test_no_monday(self):
        """Non-mondays are rejected from PlannedWork.weeks"""
        pw = factories.PlannedWorkFactory.create(weeks=[dt.date(2020, 6, 21)])

        msg = ["Only mondays allowed, but field contains 21.06.2020."]

        with self.assertRaises(ValidationError) as cm:
            pw.clean_fields(exclude=["weeks"])
        self.assertEqual(list(cm.exception), msg)

        pw.weeks = [dt.date(2020, 6, 22)]
        pw.full_clean()  # Does not raise
        self.assertEqual(pw.pretty_from_until, "22.06.2020 – 28.06.2020")

        pr = factories.PlanningRequestFactory.create()
        pr.full_clean()

        pr.earliest_start_on = dt.date(2020, 6, 14)
        pr.completion_requested_on = dt.date(2020, 6, 21)

        with self.assertRaises(ValidationError) as cm:
            pr.clean_fields()

        msg = [
            ("earliest_start_on", ["Only mondays allowed."]),
            ("completion_requested_on", ["Only mondays allowed."]),
        ]
        self.assertEqual(list(cm.exception), msg)

        pr = factories.PlanningRequestFactory.create()
        pr.completion_requested_on = pr.earliest_start_on

        msg = ["Allow at least one week for the work please."]

        with self.assertRaises(ValidationError) as cm:
            pr.clean_fields(exclude=["completion_requested_on"])

        self.assertEqual(list(cm.exception), msg)

    def test_reporting_smoke(self):
        """Smoke test the planned work report"""
        pw = factories.PlannedWorkFactory.create(weeks=[monday()])

        factories.EmploymentFactory.create(user=pw.user, date_from=dt.date(2020, 1, 1))
        service = factories.ServiceFactory.create(project=pw.project)
        factories.LoggedHoursFactory.create(rendered_by=pw.user, service=service)
        factories.AbsenceFactory.create(user=pw.user)
        pr = factories.PlanningRequestFactory.create(
            project=pw.project,
            earliest_start_on=monday() - dt.timedelta(days=21),
            completion_requested_on=monday() + dt.timedelta(days=700),
        )
        pr.receivers.add(pw.user)

        report = reporting.user_planning(pw.user)
        self.assertAlmostEqual(sum(report["by_week"]), Decimal("26"))
        self.assertEqual(len(report["projects_offers"]), 1)

        report = reporting.project_planning(pw.project)
        self.assertAlmostEqual(sum(report["by_week"]), Decimal("26"))
        self.assertEqual(len(report["projects_offers"]), 1)

        team = factories.TeamFactory.create()
        team.members.add(pw.user)
        report = reporting.team_planning(team)
        self.assertAlmostEqual(sum(report["by_week"]), Decimal("26"))
        self.assertEqual(len(report["projects_offers"]), 1)

        pw2 = factories.PlannedWorkFactory.create(
            project=pw.project,
            user=pw.user,
            weeks=[monday()],
            request=pr,
        )
        report = reporting.user_planning(pw.user)
        self.assertAlmostEqual(sum(report["by_week"]), Decimal("46"))
        self.assertEqual(len(report["projects_offers"]), 1)

        work_list = report["projects_offers"][0]["offers"][0]["work_list"]
        self.assertEqual(len(work_list), 3)
        self.assertEqual(work_list[0]["work"]["id"], pr.id)
        self.assertEqual(work_list[1]["work"]["id"], pw2.id)
        self.assertEqual(work_list[2]["work"]["id"], pw.id)

    def test_planning_search_forms(self):
        """Planning request search form branch test"""

        project = factories.ProjectFactory.create()
        pr = factories.PlanningRequestFactory.create()
        pw = factories.PlannedWorkFactory.create(weeks=[dt.date(2020, 6, 22)])

        rf = RequestFactory()

        for form_class, model, instances in [
            (PlanningRequestSearchForm, PlanningRequest, [pr]),
            (PlannedWorkSearchForm, PlannedWork, [pw]),
        ]:
            req = rf.get("/")
            req.user = project.owned_by
            form = form_class(req.GET, request=req)
            self.assertTrue(form.is_valid())
            queryset = form.filter(model.objects.all())
            self.assertEqual(list(queryset), instances)

            req = rf.get("/?project={}".format(project.pk))
            req.user = project.owned_by
            form = form_class(req.GET, request=req)
            self.assertTrue(form.is_valid())
            queryset = form.filter(model.objects.all())
            self.assertEqual(list(queryset), [])

    def test_planning_request_form(self):
        """Create and update a planning request"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        offer = factories.OfferFactory.create()

        response = self.client.get(project.urls["createrequest"])
        self.assertNotContains(response, offer.code)
        # print(response, response.content.decode("utf-8"))

        response = self.client.post(
            project.urls["createrequest"],
            {
                "modal-title": "Request",
                "modal-earliest_start_on": "2020-06-29",
                "modal-completion_requested_on": "2020-07-27",
                "modal-requested_hours": "40",
                "modal-receivers": [offer.owned_by.id, project.owned_by.id],
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

        pr = PlanningRequest.objects.get()
        self.assertEqual(
            pr.weeks,
            [
                dt.date(2020, 6, 29),
                dt.date(2020, 7, 6),
                dt.date(2020, 7, 13),
                dt.date(2020, 7, 20),
            ],
        )
        self.assertEqual(set(pr.receivers.all()), {offer.owned_by, project.owned_by})

        response = self.client.post(
            pr.urls["update"],
            {
                "modal-title": "Request",
                "modal-earliest_start_on": "2020-06-29",
                "modal-completion_requested_on": "2020-07-27",
                "modal-requested_hours": "40",
                "modal-receivers": [offer.owned_by.id],
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(set(pr.receivers.all()), {offer.owned_by})

    def test_planned_work_with_offer(self):
        """Planned work with offer preselection"""
        offer = factories.OfferFactory.create()
        self.client.force_login(offer.owned_by)

        response = self.client.get(
            offer.project.urls["creatework"] + "?offer={}".format(offer.pk)
        )
        self.assertContains(
            response,
            '<option value="{}" selected>{}</option>'.format(offer.pk, offer),
            html=True,
        )

    def test_planned_work_crud(self):
        """Create, update and delete planned work"""
        pr = factories.PlanningRequestFactory.create(
            earliest_start_on=monday(),
            completion_requested_on=monday() + dt.timedelta(days=14),
        )
        self.client.force_login(pr.created_by)

        response = self.client.get(pr.project.urls["creatework"] + "?request=bla")
        self.assertEqual(response.status_code, 200)  # No crash

        response = self.client.post(
            pr.project.urls["creatework"],
            {
                "modal-user": pr.created_by.id,
                "modal-title": "bla",
                "modal-planned_hours": 50,
                "modal-weeks": [monday().isoformat()],
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

        pw = PlannedWork.objects.get()
        response = self.client.post(
            pw.urls["update"],
            {
                "modal-user": pr.created_by.id,
                "modal-title": "bla",
                "modal-planned_hours": 50,
                "modal-weeks": [monday().isoformat()],
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)

        response = self.client.post(
            pr.project.urls["creatework"] + "?request={}".format(pr.id),
            {
                "modal-request": pr.id,
                "modal-user": pr.created_by.id,
                "modal-title": "bla",
                "modal-planned_hours": 50,
                "modal-weeks": [
                    monday().isoformat(),
                    (monday() + dt.timedelta(days=7)).isoformat(),
                ],
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        # print(response, response.content.decode("utf-8"))
        self.assertEqual(response.status_code, 201)

        response = self.client.post(
            pr.project.urls["creatework"] + "?request={}".format(pr.id),
            {
                "modal-request": pr.id,
                "modal-user": pr.created_by.id,
                "modal-title": "bla",
                "modal-planned_hours": 50,
                "modal-weeks": [
                    monday().isoformat(),
                    (monday() + dt.timedelta(days=14)).isoformat(),
                ],
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "weeks-outside-request")

    def test_replanning(self):
        """Moving planned work between requests"""

        pr1 = factories.PlanningRequestFactory.create(requested_hours=50)
        pr2 = factories.PlanningRequestFactory.create(requested_hours=50)

        pw = factories.PlannedWorkFactory.create(
            request=pr1, weeks=[monday()], planned_hours=20
        )

        pr1.refresh_from_db()
        pr2.refresh_from_db()
        self.assertEqual(pr1.planned_hours, 20)
        self.assertEqual(pr2.planned_hours, 0)

        pw.request = pr2
        pw.save()

        pr1.refresh_from_db()
        pr2.refresh_from_db()
        self.assertEqual(pr1.planned_hours, 0)
        self.assertEqual(pr2.planned_hours, 20)

        pw.delete()

        pr1.refresh_from_db()
        pr2.refresh_from_db()
        self.assertEqual(pr1.planned_hours, 0)
        self.assertEqual(pr2.planned_hours, 0)

    def test_receivers_with_work(self):
        """receivers_with_work returns all requested and planned work"""

        pr = factories.PlanningRequestFactory.create()
        only_receiver = factories.UserFactory.create()
        pr.receivers.add(only_receiver)
        only_pw = factories.PlannedWorkFactory.create(
            project=pr.project, request=pr, weeks=[monday()]
        )
        both = factories.PlannedWorkFactory.create(
            project=pr.project, request=pr, weeks=[monday()]
        )
        pr.receivers.add(both.user)

        self.assertEqual(set(pr.receivers.all()), {both.user, only_receiver})
        self.assertEqual(len(pr.receivers_with_work), 3)

        receivers = dict(pr.receivers_with_work)
        self.assertEqual(receivers[only_receiver], [])
        self.assertEqual(receivers[both.user], [both])
        self.assertEqual(receivers[only_pw.user], [only_pw])

    def test_planning_views(self):
        """The planning views do not crash"""
        user = factories.UserFactory.create()
        team = factories.TeamFactory.create()
        project = factories.ProjectFactory.create()

        self.client.force_login(user)

        response = self.client.get(user.urls["planning"])
        self.assertContains(response, 'id="planning-data"')

        response = self.client.get(team.urls["planning"])
        self.assertContains(response, 'id="planning-data"')

        response = self.client.get(project.urls["planning"])
        self.assertContains(response, 'id="planning-data"')

    def test_this_week_index(self):
        """this_week_index is None if current week isn't part of the report"""
        pw = factories.PlannedWorkFactory.create(weeks=[dt.date(2020, 6, 22)])

        report = reporting.project_planning(pw.project)
        self.assertIsNone(report["this_week_index"])

    def test_planning_request_notification(self):
        """Receivers of a planning request are notified"""
        pr = factories.PlanningRequestFactory.create()
        pr.receivers.add(
            factories.UserFactory.create(),
            factories.UserFactory.create(),
            factories.UserFactory.create(),
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("New planning request", mail.outbox[0].subject)
        self.assertEqual(len(mail.outbox[0].to), 3)
        self.assertEqual(len(mail.outbox[0].reply_to), 4)

    def test_declined_offer_warning(self):
        """Warn when offer is declined"""
        offer = factories.OfferFactory.create(status=factories.Offer.DECLINED)
        self.client.force_login(offer.owned_by)

        response = self.client.post(
            offer.project.urls["creatework"],
            {
                "modal-user": offer.owned_by_id,
                "modal-title": "bla",
                "modal-planned_hours": 50,
                "modal-weeks": [monday().isoformat()],
                "modal-offer": offer.id,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, 'value="offer-is-declined"')

        response = self.client.post(
            offer.project.urls["createrequest"],
            {
                "modal-title": "Request",
                "modal-earliest_start_on": "2020-06-29",
                "modal-completion_requested_on": "2020-07-27",
                "modal-requested_hours": "40",
                "modal-receivers": [offer.owned_by.id],
                "modal-offer": offer.id,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, 'value="offer-is-declined"')

    def test_link_or_none_of_planning_requests(self):
        """Planning requests have a specific implementation of link_or_none"""
        pr = factories.PlanningRequestFactory.create()
        self.assertEqual(pr.html_link(), link_or_none(pr))

    def test_planned_work_ranges(self):
        """Range detection works"""
        pw = factories.PlannedWorkFactory.create(
            weeks=[
                dt.date(2020, 6, 22),
                dt.date(2020, 6, 29),
                # dt.date(2020, 7, 6),
                dt.date(2020, 7, 13),
                dt.date(2020, 7, 20),
            ]
        )
        self.assertEqual(
            list(pw.ranges),
            [
                {
                    "from": dt.date(2020, 6, 22),
                    "until": dt.date(2020, 6, 29),
                    "pretty": "22.06.2020 – 05.07.2020",
                },
                {
                    "from": dt.date(2020, 7, 13),
                    "until": dt.date(2020, 7, 20),
                    "pretty": "13.07.2020 – 26.07.2020",
                },
            ],
        )
        self.assertEqual(pw.pretty_planned_hours, "20.0h in 4 weeks (5.0h per week)")

    def test_initialize_form_using_offer(self):
        """Initializing planning requests and planned work using offers"""

        offer = factories.OfferFactory.create(
            title="Testing title",
            description="Testing description",
        )
        self.client.force_login(offer.owned_by)

        response = self.client.get(
            offer.project.urls["createrequest"] + f"?plan_offer={offer.pk}"
        )
        self.assertContains(response, 'value="Testing title"')
        self.assertContains(response, "Testing description")

        response = self.client.get(
            offer.project.urls["creatework"] + f"?plan_offer={offer.pk}"
        )
        self.assertContains(response, 'value="Testing title"')
        self.assertContains(response, "Testing description")

        response = self.client.get(
            offer.project.urls["createrequest"] + "?plan_offer=bla"
        )
        self.assertEqual(response.status_code, 200)  # No crash

        response = self.client.get(offer.project.urls["creatework"] + "?plan_offer=bla")
        self.assertEqual(response.status_code, 200)  # No crash

    def test_initialize_form_using_service(self):
        """Initializing planning requests and planned work using services"""

        service = factories.ServiceFactory.create(
            title="Testing title",
            description="Testing description",
            effort_hours=20,
        )
        self.client.force_login(service.project.owned_by)

        response = self.client.get(
            service.project.urls["createrequest"] + f"?service={service.pk}"
        )
        self.assertContains(response, f'value="{service.project.title}: Testing title"')
        self.assertContains(response, "Testing description")
        self.assertContains(response, 'value="20.0"')

        response = self.client.get(
            service.project.urls["creatework"] + f"?service={service.pk}"
        )
        self.assertContains(response, f'value="{service.project.title}: Testing title"')
        self.assertContains(response, "Testing description")
        self.assertContains(response, 'value="20.0"')

        response = self.client.get(
            service.project.urls["createrequest"] + "?service=bla"
        )
        self.assertEqual(response.status_code, 200)  # No crash

        response = self.client.get(service.project.urls["creatework"] + "?service=bla")
        self.assertEqual(response.status_code, 200)  # No crash
