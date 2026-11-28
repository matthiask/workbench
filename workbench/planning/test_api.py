import datetime as dt
import re

from django.test import Client, TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.offers.models import Offer
from workbench.tools.validation import in_days, monday


class PlanningAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def test_context(self):
        """The context contains what's needed to plan and the import schema"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        factories.OfferFactory.create(project=project, status=Offer.DECLINED)
        factories.ServiceFactory.create(
            project=project, offer=offer, title="Design", service_hours=20
        )
        milestone = factories.MilestoneFactory.create(project=project, date=in_days(30))
        factories.PlannedWorkFactory.create(
            project=project, milestone=milestone, weeks=[monday()]
        )
        factories.AbsenceFactory.create(user=project.owned_by, reason="sickness")
        factories.AbsenceFactory.create(starts_on=in_days(-30), ends_on=in_days(-20))
        factories.AbsenceFactory.create(reason="correction")
        inactive = factories.UserFactory.create(is_active=False)
        service_type = factories.service_types().consulting

        url = f"/api/projects/{project.pk}/planning/context/"
        self.assertEqual(self.client.get(url).status_code, 401)

        self.client.force_login(project.owned_by)
        data = self.client.get(url).json()

        self.assertEqual(data["project"]["code"], project.code)
        self.assertEqual([o["code"] for o in data["offers"]], [offer.code])
        self.assertEqual(data["offers"][0]["services"][0]["title"], "Design")
        self.assertEqual(data["milestones"][0]["id"], milestone.pk)
        self.assertEqual(data["planned_work"][0]["milestone"], milestone.pk)
        self.assertEqual(data["planned_work"][0]["weeks"], [monday().isoformat()])
        self.assertEqual(
            data["absences"],
            [
                {
                    "user": project.owned_by._short_name,
                    "starts_on": dt.date.today().isoformat(),
                    "ends_on": None,
                    "days": "1.00",
                }
            ],
        )

        # Only active users
        short_names = [user["short_name"] for user in data["users"]]
        self.assertIn(project.owned_by._short_name, short_names)
        self.assertNotIn(inactive._short_name, short_names)
        self.assertEqual(data["project"]["owned_by"], project.owned_by._short_name)
        self.assertNotIn("@", str(data))

        work = data["import_schema"]["$defs"]["PlannedWorkIn"]["properties"]
        self.assertEqual(work["user"]["anyOf"][0]["enum"], short_names)
        self.assertIn(service_type.title, work["service_type"]["anyOf"][0]["enum"])
        self.assertEqual(work["offer"]["anyOf"][0]["enum"], [offer.code])

        self.assertEqual(
            self.client.get("/api/projects/0/planning/context/").status_code, 404
        )

    def test_import(self):
        """Importing adds milestones and planned work, or nothing at all"""
        project = factories.ProjectFactory.create()
        user = project.owned_by
        offer = factories.OfferFactory.create(project=project)
        declined = factories.OfferFactory.create(project=project, status=Offer.DECLINED)
        existing = factories.MilestoneFactory.create(project=project, date=in_days(90))
        factories.service_types()
        self.client.force_login(user)

        url = f"/api/projects/{project.pk}/planning/import/"
        start = monday() + dt.timedelta(days=14)
        data = {
            "milestones": [
                {"key": "golive", "title": "Go-Live", "date": in_days(60).isoformat()}
            ],
            "planned_work": [
                {
                    "title": "Concept",
                    "user": user._short_name,
                    "service_type": "consulting",
                    "offer": offer.code,
                    "milestone": "golive",
                    # Not a monday, and listed twice
                    "weeks": [
                        (start + dt.timedelta(days=2)).isoformat(),
                        start.isoformat(),
                    ],
                    "planned_hours": 12.25,
                },
                {
                    "title": "Production",
                    # Short names are matched case-insensitively
                    "user": user._short_name.upper(),
                    "service_type": "production",
                    "milestone": existing.pk,
                    "weeks": [start.isoformat()],
                    "planned_hours": 20,
                    "is_provisional": False,
                },
            ],
        }

        response = self.client.post(
            url + "?dry_run=true", data, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["milestones"][0]["id"], None)
        self.assertEqual(result["planned_work"][0]["milestone"], "Go-Live")
        self.assertEqual(
            result["planned_work"][0]["milestone_id"], result["milestones"][0]["id"]
        )
        self.assertEqual(result["planned_work"][0]["weeks"], [start.isoformat()])
        self.assertEqual(result["planned_work"][0]["planned_hours"], "12.2")
        self.assertEqual(result["warnings"], [])
        self.assertEqual(project.planned_work.count(), 0)
        self.assertEqual(project.milestones.count(), 1)

        response = self.client.post(url, data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        concept, production = project.planned_work.order_by("pk")
        self.assertEqual(concept.milestone.title, "Go-Live")
        self.assertEqual(concept.offer, offer)
        self.assertEqual(concept.created_by, user)
        self.assertTrue(concept.is_provisional)
        self.assertEqual(production.milestone, existing)
        self.assertFalse(production.is_provisional)

        # Invalid references are reported per entry, and nothing is saved
        data["milestones"].append(data["milestones"][0])
        data["planned_work"][0] |= {
            "user": "nobody",
            "service_type": "unknown",
            "offer": declined.code,
            "milestone": "missing",
        }
        data["planned_work"][1]["weeks"] = [in_days(100).isoformat()]
        response = self.client.post(url, data, content_type="application/json")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"][2:] for error in response.json()["detail"]],
            [
                ["milestones", 1, "key"],
                ["planned_work", 0, "user"],
                ["planned_work", 0, "service_type"],
                ["planned_work", 0, "offer"],
                ["planned_work", 0, "milestone"],
            ],
        )
        self.assertEqual(project.planned_work.count(), 2)
        self.assertEqual(project.milestones.count(), 2)

        # Work after the milestone is only a warning
        response = self.client.post(
            url + "?dry_run=true",
            {"planned_work": [data["planned_work"][1]]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [warning["loc"][2:] for warning in response.json()["warnings"]],
            [["planned_work", 0, "weeks"]],
        )

        # The schema is enforced too
        response = self.client.post(
            url,
            {"planned_work": [{"title": "Nothing else"}]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)

    def test_import_milestone_phase_after_date(self):
        """The phase of a milestone doesn't start after the milestone"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)
        response = self.client.post(
            f"/api/projects/{project.pk}/planning/import/",
            {
                "milestones": [
                    {
                        "key": "golive",
                        "title": "Go-Live",
                        "date": in_days(60).isoformat(),
                        "phase_starts_on": in_days(61).isoformat(),
                    }
                ],
                "planned_work": [],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422, response.content)
        self.assertEqual(project.milestones.count(), 0)

    def test_import_milestone_keeps_omitted_fields(self):
        """Updating a milestone keeps the phase and hours which aren't given"""
        project = factories.ProjectFactory.create()
        milestone = factories.MilestoneFactory.create(
            project=project,
            date=in_days(60),
            phase_starts_on=in_days(30),
            estimated_total_hours=40,
        )
        self.client.force_login(project.owned_by)
        response = self.client.post(
            f"/api/projects/{project.pk}/planning/import/",
            {
                "milestones": [
                    {
                        "id": milestone.pk,
                        "title": "Launch",
                        "date": in_days(70).isoformat(),
                    }
                ],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        milestone.refresh_from_db()
        self.assertEqual(milestone.date, in_days(70))
        self.assertEqual(milestone.phase_starts_on, in_days(30))
        self.assertEqual(milestone.estimated_total_hours, 40)

    def test_import_work_on_deleted_milestone(self):
        """Work can't be put on a milestone which is deleted in the same
        import"""
        project = factories.ProjectFactory.create()
        user = factories.UserFactory.create(_short_name="ab")
        service_type = factories.service_types().consulting
        milestone = factories.MilestoneFactory.create(project=project, date=in_days(60))
        self.client.force_login(project.owned_by)
        response = self.client.post(
            f"/api/projects/{project.pk}/planning/import/",
            {
                "planned_work": [
                    {
                        "title": "Design",
                        "user": user.get_short_name(),
                        "service_type": service_type.title,
                        "planned_hours": 10,
                        "weeks": [monday().isoformat()],
                        "milestone": milestone.pk,
                    }
                ],
                "delete_milestones": [milestone.pk],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422, response.content)
        self.assertEqual(
            [error["loc"][2:] for error in response.json()["detail"]],
            [["planned_work", 0, "milestone"]],
        )
        self.assertTrue(project.milestones.exists())

    def test_deletions_delete_emptied_milestones(self):
        """Deleting planned work through the API deletes its future
        milestones left without work, also those deleted explicitly"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        def work():
            milestone = factories.MilestoneFactory.create(
                project=project, date=in_days(60)
            )
            return factories.PlannedWorkFactory.create(
                project=project, milestone=milestone, weeks=[monday()]
            )

        deleted = work()
        response = self.client.delete(f"/api/planning/work/{deleted.pk}/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(project.milestones.exists())

        imported, both = work(), work()
        response = self.client.post(
            f"/api/projects/{project.pk}/planning/import/",
            {
                "delete_planned_work": [imported.pk, both.pk],
                "delete_milestones": [both.milestone_id],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(project.milestones.exists())

    def test_import_unchanged_context(self):
        """Planned work sent back unchanged is accepted, also with users who
        left and offers which have been declined since"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        left = factories.UserFactory.create(_short_name="zz")
        factories.PlannedWorkFactory.create(
            project=project, user=left, weeks=[monday()]
        )
        factories.PlannedWorkFactory.create(
            project=project, offer=offer, weeks=[monday()]
        )
        left.is_active = False
        left.save()
        offer.status = Offer.DECLINED
        offer.save()
        self.client.force_login(project.owned_by)

        context = self.client.get(
            f"/api/projects/{project.pk}/planning/context/"
        ).json()
        self.assertEqual(
            {pw["user"] for pw in context["planned_work"]},
            {"zz", project.planned_work.exclude(user=left).get().user._short_name},
        )
        response = self.client.post(
            f"/api/projects/{project.pk}/planning/import/",
            {"milestones": [], "planned_work": context["planned_work"]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        # Changing to them isn't possible
        pw = project.planned_work.exclude(user=left).get()
        response = self.client.patch(
            f"/api/planning/work/{pw.pk}/",
            {"user": "zz"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)

    def test_import_unchanged_user_without_short_name(self):
        """Planned work of users without a short name has a null user in the
        context, sending it back unchanged works but null never sets a user"""
        project = factories.ProjectFactory.create()
        anonymous = factories.UserFactory.create(_short_name="")
        pw = factories.PlannedWorkFactory.create(
            project=project, user=anonymous, weeks=[monday()]
        )
        other = factories.PlannedWorkFactory.create(project=project, weeks=[monday()])
        self.client.force_login(project.owned_by)

        context = self.client.get(
            f"/api/projects/{project.pk}/planning/context/"
        ).json()
        work = {item["id"]: item for item in context["planned_work"]}
        self.assertIsNone(work[pw.pk]["user"])
        response = self.client.post(
            f"/api/projects/{project.pk}/planning/import/",
            {"milestones": [], "planned_work": context["planned_work"]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        pw.refresh_from_db()
        self.assertEqual(pw.user, anonymous)

        # Null doesn't remove the user of other planned work
        response = self.client.patch(
            f"/api/planning/work/{other.pk}/",
            {"user": None},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)

    def test_import_page(self):
        """The import page contains the prompt and is linked from the planning"""
        project = factories.ProjectFactory.create(title="Relaunch für Kunde")
        offer = factories.OfferFactory.create(project=project)
        self.client.force_login(project.owned_by)

        response = self.client.get(project.urls["planning"])
        self.assertContains(response, project.urls["planning_import"])

        response = self.client.get(project.urls["planning_import"])
        self.assertContains(response, "Relaunch für Kunde")
        self.assertContains(response, offer.code)
        self.assertContains(response, "PlannedWorkIn")
        self.assertContains(response, f"/api/projects/{project.pk}/planning/import/")
        self.assertNotContains(response, project.owned_by.email)

    def test_import_csrf(self):
        """Session authenticated requests need a CSRF token"""
        project = factories.ProjectFactory.create()
        client = Client(enforce_csrf_checks=True)
        client.force_login(project.owned_by)
        url = f"/api/projects/{project.pk}/planning/import/?dry_run=true"

        response = client.post(url, {}, content_type="application/json")
        self.assertEqual(response.status_code, 403)

        client.get(project.urls["planning_import"])  # Sets the CSRF cookie
        response = client.post(
            url,
            {},
            content_type="application/json",
            headers={"X-CSRFToken": client.cookies["csrftoken"].value},
        )
        self.assertEqual(response.status_code, 200)

    def test_drag_csrf(self):
        """Dragging work in the planning saves it with the page's CSRF token"""
        pw = factories.PlannedWorkFactory.create(weeks=[monday()])
        client = Client(enforce_csrf_checks=True)
        client.force_login(pw.user)

        response = client.get(pw.project.urls["planning"])
        token = re.search(r'data-csrf-token="([^"]+)"', response.content.decode())
        week = monday() + dt.timedelta(days=7)
        response = client.patch(
            f"/api/planning/work/{pw.pk}/",
            {"weeks": [week.isoformat()]},
            content_type="application/json",
            headers={"X-CSRFToken": token[1]},
        )
        self.assertEqual(response.status_code, 200)
        pw.refresh_from_db()
        self.assertEqual(pw.weeks, [week])

    def test_null_for_required_fields(self):
        """Fields which can't be empty reject null"""
        pw = factories.PlannedWorkFactory.create(weeks=[monday()])
        self.client.force_login(pw.user)
        for field in [
            "title",
            "user",
            "weeks",
            "planned_hours",
            "is_provisional",
        ]:
            with self.subTest(field=field):
                response = self.client.patch(
                    f"/api/planning/work/{pw.pk}/",
                    {field: None},
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 422)
                self.assertEqual(
                    response.json()["detail"][0]["msg"],
                    "This field cannot be null.",
                )

    def test_export_at_most_ten_years(self):
        """Exports cover at most ten years, they list every week"""
        user = factories.UserFactory.create()
        self.client.force_login(user)
        response = self.client.get(
            "/api/planning/export/?since=2020-01-01&until=2029-12-31"
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.get(
            "/api/planning/export/?since=2020-01-01&until=2030-01-07"
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"][0]["loc"], ["query", "until"])

        # Also the period of a project's planned work
        work = factories.PlannedWorkFactory.create(
            weeks=[monday(), monday(in_days(11 * 365))]
        )
        response = self.client.get(f"/api/planning/export/?project={work.project_id}")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"][0]["loc"], ["query", "until"])

    def test_export(self):
        """Planned work, milestones and capacity of a period or a project"""
        user = factories.UserFactory.create(_short_name="ab")
        factories.EmploymentFactory.create(user=user, date_from=in_days(-30))
        project = factories.ProjectFactory.create(
            campaign=factories.CampaignFactory.create()
        )
        week = monday()
        work = factories.PlannedWorkFactory.create(
            project=project,
            user=user,
            title="Design",
            planned_hours=20,
            weeks=[week, week + dt.timedelta(days=7)],
        )
        later = factories.PlannedWorkFactory.create(
            project=project,
            title="Launch",
            planned_hours=5,
            weeks=[week + dt.timedelta(days=140)],
            is_provisional=True,
        )
        milestone = factories.MilestoneFactory.create(
            project=project, date=week + dt.timedelta(days=11)
        )
        self.client.force_login(user)

        data = self.client.get("/api/planning/export/").json()
        self.assertEqual(data["since"], week.isoformat())
        self.assertEqual(len(data["weeks"]), 12)
        self.assertEqual([w["id"] for w in data["planned_work"]], [work.id])
        self.assertEqual(data["planned_work"][0]["hours_per_week"], "10.0")
        self.assertEqual(data["weeks"][0]["planned"], "10.0")
        self.assertEqual([m["id"] for m in data["milestones"]], [milestone.id])
        self.assertIsNone(data["capacity"])

        # A project's whole planning
        data = self.client.get("/api/planning/export/", {"project": project.pk}).json()
        self.assertEqual([w["id"] for w in data["planned_work"]], [work.id, later.id])
        self.assertEqual(len(data["weeks"]), 21)
        self.assertEqual(data["weeks"][-1]["provisional"], "5.0")
        data = self.client.get(
            "/api/planning/export/", {"campaign": project.campaign_id}
        )
        self.assertEqual(len(data.json()["planned_work"]), 2)

        # Capacity of users, the period overrides the project's
        data = self.client.get(
            "/api/planning/export/",
            {
                "user": "ab",
                "since": week.isoformat(),
                "until": week.isoformat(),
            },
        ).json()
        self.assertEqual(len(data["weeks"]), 1)
        self.assertEqual(data["planned_work"][0]["hours_in_period"], "10.0")
        [capacity] = data["capacity"]
        self.assertEqual(capacity["user"], "ab")
        self.assertEqual(list(capacity["weeks"]), [week.isoformat()])

        data = self.client.get("/api/planning/export/", {"project": 0}).json()
        self.assertEqual(data["since"], None)
        self.assertEqual(data["planned_work"], [])

    def test_update_and_delete_by_import(self):
        """Entries with an ID update existing ones, deletions are explicit"""
        project = factories.ProjectFactory.create()
        factories.service_types()
        milestone = factories.MilestoneFactory.create(project=project, date=in_days(60))
        pw = factories.PlannedWorkFactory.create(
            project=project, weeks=[monday()], planned_hours=10, is_provisional=True
        )
        doomed = factories.PlannedWorkFactory.create(project=project, weeks=[monday()])
        other = factories.PlannedWorkFactory.create(weeks=[monday()])
        self.client.force_login(project.owned_by)
        url = f"/api/projects/{project.pk}/planning/import/"

        # The context has the IDs for the round trip
        context = self.client.get(f"/api/projects/{project.pk}/planning/context/")
        self.assertEqual(
            {row["id"] for row in context.json()["planned_work"]}, {pw.pk, doomed.pk}
        )

        response = self.client.post(
            url,
            {
                "milestones": [
                    {
                        "id": milestone.pk,
                        "title": "Launch",
                        "date": in_days(70).isoformat(),
                    }
                ],
                "planned_work": [{"id": pw.pk, "is_provisional": False}],
                "delete_planned_work": [doomed.pk],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        pw.refresh_from_db()
        milestone.refresh_from_db()
        self.assertFalse(pw.is_provisional)
        self.assertEqual(pw.planned_hours, 10)  # Left out, kept
        self.assertEqual(milestone.title, "Launch")
        self.assertFalse(project.planned_work.filter(pk=doomed.pk).exists())

        # Other projects' work can't be changed or deleted through this project
        response = self.client.post(
            url,
            {
                "planned_work": [{"id": other.pk, "is_provisional": False}],
                "delete_planned_work": [other.pk],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(len(response.json()["detail"]), 2)

    def test_single_planned_work(self):
        """Planned work is added, changed and deleted one by one"""
        project = factories.ProjectFactory.create()
        factories.service_types()
        user = project.owned_by
        self.client.force_login(user)

        response = self.client.post(
            f"/api/projects/{project.pk}/planning/work/",
            {
                "title": "Concept",
                "user": user._short_name,
                "service_type": "consulting",
                "weeks": [monday().isoformat()],
                "planned_hours": 8,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        (created,) = response.json()["planned_work"]
        self.assertTrue(created["is_provisional"])
        url = f"/api/planning/work/{created['id']}/"

        response = self.client.patch(
            url,
            {
                "is_provisional": False,
                "weeks": [(monday() + dt.timedelta(days=7)).isoformat()],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        (updated,) = response.json()["planned_work"]
        self.assertFalse(updated["is_provisional"])
        self.assertEqual(updated["title"], "Concept")
        self.assertEqual(updated["planned_hours"], "8.0")

        response = self.client.patch(
            url, {"user": "nobody"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422)

        response = self.client.delete(url + "?dry_run=true")
        self.assertEqual(response.json()["deleted_planned_work"], [created["id"]])
        self.assertTrue(project.planned_work.exists())
        self.client.delete(url)
        self.assertFalse(project.planned_work.exists())

    def test_planned_work_service_type_and_declined_offer(self):
        """Like the form, planned work needs a service type and declined
        offers are a warning which can be ignored"""
        service_types = factories.service_types()
        pw = factories.PlannedWorkFactory.create(
            weeks=[monday()], service_type=service_types.consulting
        )
        declined = factories.OfferFactory.create(
            project=pw.project, status=Offer.DECLINED
        )
        self.client.force_login(pw.user)
        url = f"/api/planning/work/{pw.pk}/"

        response = self.client.patch(
            url, {"service_type": None}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422, response.content)
        (error,) = response.json()["detail"]
        self.assertEqual(error["loc"], ["body", "data", "service_type"])

        response = self.client.patch(
            url, {"offer": declined.code}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422, response.content)
        (error,) = response.json()["detail"]
        self.assertEqual(error["code"], "offer-is-declined")
        self.assertEqual(error["loc"], ["body", "data", "offer"])

        response = self.client.patch(
            url + "?ignore_warnings=offer-is-declined",
            {"offer": declined.code},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        pw.refresh_from_db()
        self.assertEqual(pw.offer, declined)

        response = self.client.post(
            f"/api/projects/{pw.project.pk}/planning/work/"
            "?ignore_warnings=offer-is-declined&dry_run=true",
            {
                "title": "Concept",
                "user": pw.user._short_name,
                "service_type": "consulting",
                "offer": declined.code,
                "weeks": [monday().isoformat()],
                "planned_hours": 8,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)

    def batch(self, data, query=""):
        return self.client.post(
            f"/api/planning/work/batch/{query}", data, content_type="application/json"
        )

    def test_batch_update(self):
        """Planned work of several projects is changed at once, through the
        web interface's batch form"""
        leaving = factories.UserFactory.create(_short_name="ub")
        taking_over = factories.UserFactory.create(_short_name="aha")
        week = monday() + dt.timedelta(days=7)
        first = factories.PlannedWorkFactory.create(
            user=leaving, weeks=[week], is_provisional=True
        )
        second = factories.PlannedWorkFactory.create(
            user=leaving, weeks=[week, week + dt.timedelta(days=7)]
        )
        other = factories.PlannedWorkFactory.create(user=leaving, weeks=[week])
        self.assertNotEqual(first.project, second.project)
        self.client.force_login(taking_over)

        data = {
            "work": [first.pk, second.pk],
            "assign_to": "AHA",
            "move_by_weeks": 1,
            "provisional": False,
        }
        response = self.batch(data, "?dry_run=true")
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()
        self.assertEqual(
            [
                (pw["id"], pw["user"], pw["is_provisional"])
                for pw in result["planned_work"]
            ],
            [(first.pk, "aha", False), (second.pk, "aha", False)],
        )
        self.assertEqual(
            result["planned_work"][1]["weeks"],
            [
                (week + dt.timedelta(days=7)).isoformat(),
                (week + dt.timedelta(days=14)).isoformat(),
            ],
        )
        first.refresh_from_db()
        self.assertEqual(first.user, leaving)

        response = self.batch(data)
        self.assertEqual(response.status_code, 200, response.content)
        for pw in [first, second, other]:
            pw.refresh_from_db()
        self.assertEqual(
            [first.user, second.user, other.user], [taking_over, taking_over, leaving]
        )
        self.assertEqual(first.weeks, [week + dt.timedelta(days=7)])
        self.assertFalse(first.is_provisional)
        self.assertEqual(other.weeks, [week])

    def test_batch_update_refused(self):
        """The batch form's rules apply: active users, open projects, no new
        weeks on closed projects"""
        pw = factories.PlannedWorkFactory.create(weeks=[monday()])
        inactive = factories.UserFactory.create(_short_name="old", is_active=False)
        closed = factories.ProjectFactory.create(closed_on=dt.date.today())
        self.client.force_login(pw.user)

        for data, loc in [
            ({"work": []}, "work"),
            ({"work": [pw.pk + 1]}, "work"),
            ({"work": [pw.pk], "assign_to": inactive._short_name}, "assign_to"),
            ({"work": [pw.pk], "project": closed.code}, "project"),
            ({"work": [pw.pk], "project": "2099-9999"}, "project"),
            ({"work": [pw.pk], "move_by_weeks": 10**9}, "move_by_weeks"),
            ({"work": [pw.pk], "move_by_weeks": -(10**9)}, "move_by_weeks"),
        ]:
            with self.subTest(data=data):
                response = self.batch(data)
                self.assertEqual(response.status_code, 422, response.content)
                (error,) = response.json()["detail"]
                self.assertEqual(error["loc"], ["body", "data", loc])

        pw.project.closed_on = dt.date.today()
        pw.project.save()
        response = self.batch({"work": [pw.pk], "move_by_weeks": 2})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"],
            [
                {
                    "loc": ["body", "data", "move_by_weeks"],
                    "msg": "The project is closed.",
                }
            ],
        )

    def test_batch_update_declined_offer(self):
        """Changing work of declined offers is a warning which can be ignored"""
        pw = factories.PlannedWorkFactory.create(
            offer=factories.OfferFactory.create(status=factories.Offer.DECLINED),
            weeks=[monday()],
        )
        self.client.force_login(pw.user)

        response = self.batch({"work": [pw.pk], "provisional": True})
        self.assertEqual(response.status_code, 422, response.content)
        (error,) = response.json()["detail"]
        self.assertEqual(error["code"], "offer-is-declined")

        response = self.batch(
            {"work": [pw.pk], "provisional": True},
            "?ignore_warnings=offer-is-declined",
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_batch_update_project_and_delete(self):
        """Work moved to another project (by code) loses its offer and
        milestone; deleting returns the IDs"""
        milestone = factories.MilestoneFactory.create(date=in_days(30))
        pw = factories.PlannedWorkFactory.create(
            project=milestone.project,
            milestone=milestone,
            offer=factories.OfferFactory.create(project=milestone.project),
            weeks=[monday()],
        )
        target = factories.ProjectFactory.create()
        self.client.force_login(pw.user)

        response = self.batch({"work": [pw.pk], "project": target.code})
        self.assertEqual(response.status_code, 200, response.content)
        (moved,) = response.json()["planned_work"]
        self.assertEqual((moved["offer"], moved["milestone"]), (None, None))
        pw.refresh_from_db()
        self.assertEqual(pw.project, target)

        response = self.batch({"work": [pw.pk], "delete": True}, "?dry_run=true")
        self.assertEqual(response.json()["deleted_planned_work"], [pw.pk])
        self.assertEqual(response.json()["planned_work"], [])
        self.assertTrue(target.planned_work.exists())
        response = self.batch({"work": [pw.pk], "delete": True})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(target.planned_work.exists())

    def test_single_milestone(self):
        """Milestones are added, changed and deleted one by one through the
        web interface's form"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)
        url = f"/api/projects/{project.pk}/planning/milestones/"

        response = self.client.post(
            url + "?dry_run=true",
            {"title": "Launch", "date": in_days(30).isoformat()},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        (created,) = response.json()["milestones"]
        self.assertIsNone(created["id"])
        self.assertEqual(created["estimated_total_hours"], "0.0")
        self.assertFalse(project.milestones.exists())

        response = self.client.post(
            url,
            {
                "title": "Launch",
                "date": in_days(30).isoformat(),
                "phase_starts_on": in_days(10).isoformat(),
                "estimated_total_hours": 40,
                "color": "#37b24d",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        (created,) = response.json()["milestones"]
        milestone = project.milestones.get()
        self.assertEqual(created["id"], milestone.pk)
        self.assertEqual(created["color"], "#37b24d")
        self.assertEqual(milestone.estimated_total_hours, 40)

        # The form's errors
        response = self.client.post(
            url,
            {"title": "Launch", "date": in_days(30).isoformat(), "color": "pink"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"][0]["loc"], ["body", "data", "color"])

        url = f"/api/planning/milestones/{milestone.pk}/"
        response = self.client.patch(
            url,
            {"phase_starts_on": in_days(31).isoformat()},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["loc"], ["body", "data", "phase_starts_on"]
        )

        # Moving the milestone before its planned work warns
        factories.PlannedWorkFactory.create(
            project=project, milestone=milestone, weeks=[monday(in_days(21))]
        )
        response = self.client.patch(
            url, {"date": in_days(14).isoformat()}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"][0]["code"], "work-after-milestone")
        response = self.client.patch(
            url + "?ignore_warnings=work-after-milestone",
            {"date": in_days(14).isoformat(), "color": None},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        (updated,) = response.json()["milestones"]
        self.assertEqual(updated["title"], "Launch")
        self.assertEqual(updated["date"], in_days(14).isoformat())
        self.assertEqual(updated["color"], "")

        response = self.client.delete(url + "?dry_run=true")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["deleted_milestones"], [milestone.pk])
        self.assertTrue(project.milestones.exists())
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(project.milestones.exists())
        self.assertIsNone(project.planned_work.get().milestone)
        self.assertEqual(self.client.delete(url).status_code, 404)

        # Closed projects get no new milestones
        project.closed_on = dt.date.today()
        project.save()
        response = self.client.post(
            f"/api/projects/{project.pk}/planning/milestones/",
            {"title": "Launch", "date": in_days(30).isoformat()},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"],
            [{"loc": ["body", "data"], "msg": "The project is closed."}],
        )

    def test_single_external_work(self):
        """External work is added, changed and deleted one by one through the
        web interface's form"""
        project = factories.ProjectFactory.create()
        factories.service_types()
        milestone = factories.MilestoneFactory.create(project=project, date=in_days(60))
        other = factories.MilestoneFactory.create(date=in_days(60))
        agency = factories.OrganizationFactory.create(name="Beispiel AG")
        self.client.force_login(project.owned_by)
        url = f"/api/projects/{project.pk}/planning/external-work/"

        # The customer and this week by default
        response = self.client.post(
            url + "?dry_run=true",
            {"title": "Photos"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        (created,) = response.json()["external_work"]
        self.assertIsNone(created["id"])
        self.assertEqual(created["provided_by_id"], project.customer_id)
        self.assertEqual(created["weeks"], [monday().isoformat()])
        self.assertFalse(project.external_work.exists())

        next_week = monday() + dt.timedelta(days=7)
        data = {
            "title": "Photos",
            "provided_by": agency.pk,
            "service_type": "consulting",
            "milestone": milestone.pk,
            # Any day of the week
            "weeks": [(next_week + dt.timedelta(days=2)).isoformat()],
            "notes": "Two days",
        }
        response = self.client.post(url, data, content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        (created,) = response.json()["external_work"]
        ew = project.external_work.get()
        self.assertEqual(created["id"], ew.pk)
        self.assertEqual(
            (created["provided_by"], created["service_type"], created["milestone"]),
            ("Beispiel AG", "consulting", "Milestone"),
        )
        self.assertEqual(ew.weeks, [next_week])
        self.assertEqual(ew.created_by, project.owned_by)

        for patch, loc in [
            ({"milestone": other.pk}, "milestone"),
            ({"service_type": "nothing"}, "service_type"),
            ({"provided_by": 0}, "provided_by"),
            ({"weeks": []}, "weeks"),
        ]:
            with self.subTest(patch=patch):
                response = self.client.post(
                    url, data | patch, content_type="application/json"
                )
                self.assertEqual(response.status_code, 422, response.content)
                self.assertEqual(
                    response.json()["detail"][0]["loc"], ["body", "data", loc]
                )

        url = f"/api/planning/external-work/{ew.pk}/"
        late = monday(in_days(70))
        response = self.client.patch(
            url, {"weeks": [late.isoformat()]}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"][0]["code"], "weeks-after-milestone")
        response = self.client.patch(
            url + "?ignore_warnings=weeks-after-milestone",
            {"weeks": [late.isoformat()], "notes": None},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        (updated,) = response.json()["external_work"]
        self.assertEqual(
            (updated["title"], updated["weeks"], updated["notes"]),
            ("Photos", [late.isoformat()], ""),
        )
        response = self.client.patch(
            url, {"milestone": None}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        ew.refresh_from_db()
        self.assertIsNone(ew.milestone)

        # In the planning context
        data = self.client.get(f"/api/projects/{project.pk}/planning/context/").json()
        self.assertEqual(
            data["external_work"],
            [
                {
                    "id": ew.pk,
                    "title": "Photos",
                    "provided_by": "Beispiel AG",
                    "service_type": "consulting",
                    "milestone": None,
                    "weeks": [late.isoformat()],
                    "notes": "",
                }
            ],
        )

        # No new weeks on closed projects
        project.closed_on = dt.date.today()
        project.save()
        response = self.client.patch(
            url,
            {"weeks": [late.isoformat(), next_week.isoformat()]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"][0]["loc"], ["body", "data", "weeks"])

        response = self.client.delete(url + "?dry_run=true")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["deleted_external_work"], [ew.pk])
        self.assertTrue(project.external_work.exists())
        self.client.delete(url)
        self.assertFalse(project.external_work.exists())
