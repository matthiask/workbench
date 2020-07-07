import datetime as dt

from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.planning import reporting
from workbench.planning.forms import PlannedWorkSearchForm, PlanningRequestSearchForm
from workbench.planning.models import PlannedWork, PlanningRequest
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

        service = factories.ServiceFactory.create(project=pw.project)
        factories.LoggedHoursFactory.create(rendered_by=pw.user, service=service)

        report = reporting.user_planning(pw.user)
        self.assertEqual(sum(report["by_week"]), 20)
        self.assertEqual(len(report["projects_offers"]), 1)

        report = reporting.project_planning(pw.project)
        self.assertEqual(sum(report["by_week"]), 20)
        self.assertEqual(len(report["projects_offers"]), 1)

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

    def test_planned_work_crud(self):
        """Create, update and delete planned work"""
        pr = factories.PlanningRequestFactory.create(
            earliest_start_on=monday(),
            completion_requested_on=monday() + dt.timedelta(days=14),
        )
        self.client.force_login(pr.created_by)

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
            pr.project.urls["creatework"],
            {
                "modal-user": pr.project.owned_by.id,
                "modal-title": "bla",
                "modal-planned_hours": 50,
                "modal-weeks": [monday().isoformat()],
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "planning-for-somebody-else")

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

        # TODO check what happens with pr.planned_hours when updating, changing
        # request and deleting work

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
