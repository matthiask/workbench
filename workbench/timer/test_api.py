import datetime as dt

from django.test import TestCase
from django.utils.translation import deactivate_all
from time_machine import travel

from workbench import factories
from workbench.timer.models import Timestamp
from workbench.tools.validation import in_days


class TimestampsAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    @travel("2026-10-30T12:00:00+01:00", tick=False)
    def test_create(self):
        """Timestamps are created now, at a time or relative to now"""
        user = factories.UserFactory.create()
        self.client.force_login(user)

        def create(**data):
            return self.client.post(
                "/api/timestamps/", data, content_type="application/json"
            )

        data = create(type="start").json()
        self.assertEqual(data["created_at"], "2026-10-30T12:00:00+01:00")
        self.assertIsNone(data["slice"]["ends_at"])
        data = create(type="stop", minutes=30, notes="Wireframes").json()
        self.assertEqual(data["created_at"], "2026-10-30T12:30:00+01:00")
        self.assertEqual(data["notes"], "Wireframes")
        # The stopped task
        self.assertEqual(data["slice"]["starts_at"], "2026-10-30T12:00:00+01:00")
        self.assertEqual(data["slice"]["hours"], "0.5")
        data = create(type="stop", time="13:30").json()
        self.assertEqual(data["created_at"], "2026-10-30T13:30:00+01:00")
        self.assertEqual(Timestamp.objects.filter(user=user).count(), 3)

        self.assertEqual(create(type="split").status_code, 422)
        self.assertEqual(create(type="stop", time="13:30", minutes=5).status_code, 422)

    @travel("2026-10-30T12:00:00+01:00", tick=False)
    def test_project_and_service(self):
        """Timestamps remember the project and the service, the slice's link
        opens the project's logbook form with the service"""
        user = factories.UserFactory.create()
        self.client.force_login(user)
        service = factories.ServiceFactory.create()
        project = service.project

        def create(**data):
            return self.client.post(
                "/api/timestamps/", data, content_type="application/json"
            )

        data = create(type="start", project=project.pk).json()
        self.assertEqual(data["project"]["id"], project.pk)
        self.assertIsNone(data["service_id"])
        # The stop has no project, the merged slice keeps the start's
        data = create(type="stop", minutes=30, notes="Wireframes").json()
        self.assertEqual(data["slice"]["project"]["id"], project.pk)
        self.assertEqual(
            data["slice"]["log_hours_url"].split("?")[0],
            f"http://testserver{project.urls['createhours']}",
        )
        self.assertNotIn("service=", data["slice"]["log_hours_url"])

        # The project is taken from the service
        create(type="start", minutes=30)
        data = create(type="stop", minutes=60, service=service.pk).json()
        self.assertEqual(data["project"]["id"], project.pk)
        self.assertEqual(data["service_id"], service.pk)
        self.assertIn(f"service={service.pk}", data["slice"]["log_hours_url"])

        other = factories.ProjectFactory.create()
        response = create(type="start", project=other.pk, service=service.pk)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(create(type="start", project=0).status_code, 422)

    def test_pinned_project_by_name(self):
        """Pinned projects can be passed as words of their code, title or
        customer"""
        user = factories.UserFactory.create()
        self.client.force_login(user)
        profond = factories.ProjectFactory.create(
            title="Website", customer=factories.OrganizationFactory(name="Profond")
        )
        forum = factories.ProjectFactory.create(title="Forum website")
        factories.ProjectFactory.create(title="Profond intranet")  # Not pinned
        closed = factories.ProjectFactory.create(
            title="Forum archive", closed_on=dt.date(2026, 1, 1)
        )
        user.pinned_projects.add(profond, forum, closed)

        def project(value):
            response = self.client.post(
                "/api/timestamps/",
                {"type": "start", "project": value},
                content_type="application/json",
            )
            return (
                response.json()["project"]["id"]
                if response.status_code == 200
                else response
            )

        self.assertEqual(project("profond"), profond.pk)
        self.assertEqual(project("FORUM"), forum.pk)
        self.assertEqual(project(profond.code), profond.pk)
        self.assertEqual(project(str(forum.pk)), forum.pk)
        self.assertContains(project("websi"), "Several projects match", status_code=422)
        self.assertContains(
            project("archive"), "No open project matches", status_code=422
        )

        # Numbers which aren't the ID of a project are searched
        kampagne = factories.ProjectFactory.create(title="Kampagne 99999")
        self.assertEqual(project("99999"), kampagne.pk)

    def test_projects_and_services_for_logging(self):
        """Timestamps only accept projects and services which accept logged
        hours, like the logbook form"""
        user = factories.UserFactory.create()
        self.client.force_login(user)

        def post(data):
            return self.client.post(
                "/api/timestamps/",
                {"type": "start"} | data,
                content_type="application/json",
            )

        closed = factories.ProjectFactory.create(closed_on=in_days(-30))
        self.assertContains(
            post({"project": closed.pk}),
            "This project has been closed too long ago.",
            status_code=422,
        )
        recently = factories.ProjectFactory.create(closed_on=in_days(-1))
        self.assertEqual(post({"project": recently.pk}).status_code, 200)
        service = factories.ServiceFactory.create(allow_logging=False)
        self.assertContains(
            post({"service": service.pk}),
            "Logging is not allowed on this service anymore.",
            status_code=422,
        )

    def test_project_words(self):
        """Every word has to match, a unique pinned project wins over the other
        open projects"""
        user = factories.UserFactory.create()
        self.client.force_login(user)
        profond = factories.OrganizationFactory.create(name="Profond")
        website = factories.ProjectFactory.create(title="Website", customer=profond)
        user.pinned_projects.add(website)
        kennzahlen = factories.ProjectFactory.create(
            title="Kennzahlen", customer=profond
        )
        factories.ProjectFactory.create(title="Manual", customer=profond)
        factories.ProjectFactory.create(title="Kennzahlen")

        def project(value):
            response = self.client.post(
                "/api/timestamps/",
                {"type": "start", "project": value},
                content_type="application/json",
            )
            return (
                response.json()["project"]["id"]
                if response.status_code == 200
                else response
            )

        self.assertEqual(project("profond"), website.pk)
        self.assertEqual(project("profond kennzahlen"), kennzahlen.pk)
        self.assertEqual(project("PROFOND  kenn"), kennzahlen.pk)
        self.assertContains(
            project("kennzahlen"), "Several projects match", status_code=422
        )
        self.assertContains(
            project("profond game"), "No open project matches", status_code=422
        )

    @travel("2026-10-30T12:00:00+01:00", tick=False)
    def test_list(self):
        """The day's slices, unlogged ones link to the logbook form"""
        user = factories.UserFactory.create()
        self.client.force_login(user)
        Timestamp.objects.create(user=user, type=Timestamp.START)
        Timestamp.objects.create(user=user, type=Timestamp.STOP, notes="Wireframes")
        hours = factories.LoggedHoursFactory.create(rendered_by=user, hours=2)

        data = self.client.get("/api/timestamps/").json()
        self.assertEqual(data["day"], "2026-10-30")
        self.assertEqual(data["logged_hours"], "2.0")
        [unlogged] = [s for s in data["slices"] if not s["is_logged"]]
        self.assertEqual(unlogged["description"], "Wireframes")
        self.assertIn("/logbook/hours/create/", unlogged["log_hours_url"])
        [logged] = [s for s in data["slices"] if s["is_logged"]]
        self.assertEqual(logged["project"]["id"], hours.service.project_id)
        self.assertIsNone(logged["log_hours_url"])

        self.assertEqual(data["weekly_hours"], "2.0")
        self.assertEqual(data["running_hours"], "0.1")

        data = self.client.get("/api/timestamps/?day=2026-10-29").json()
        self.assertEqual(data["slices"], [])
        self.assertEqual(data["weekly_hours"], "2.0")
        self.assertIsNone(data["running_since"])

    def test_delete(self):
        """Timestamps can be deleted, the latest of today undone"""
        user = factories.UserFactory.create()
        self.client.force_login(user)
        first = Timestamp.objects.create(user=user, type=Timestamp.START)
        latest = Timestamp.objects.create(user=user, type=Timestamp.STOP)
        other = Timestamp.objects.create(
            user=factories.UserFactory.create(), type=Timestamp.STOP
        )

        third = Timestamp.objects.create(user=user, type=Timestamp.STOP)

        data = self.client.get("/api/timestamps/").json()
        self.assertEqual(
            [s["timestamp_code"] for s in data["slices"]], ["T2", "T3"]
        )  # The start and the first stop are merged into one slice

        response = self.client.delete("/api/timestamps/latest/")
        self.assertEqual(response.json()["id"], third.pk)
        self.assertEqual(response.json()["code"], "T3")
        response = self.client.delete(f"/api/timestamps/{other.pk}/")
        self.assertEqual(response.status_code, 404)
        response = self.client.delete("/api/timestamps/t2/")
        self.assertEqual(response.json()["id"], latest.pk)
        response = self.client.delete("/api/timestamps/T2/")
        self.assertEqual(response.status_code, 404)
        response = self.client.delete("/api/timestamps/T1/?day=2020-01-01")
        self.assertEqual(response.status_code, 404)
        response = self.client.delete("/api/timestamps/bla/")
        self.assertEqual(response.status_code, 404)
        response = self.client.delete(f"/api/timestamps/{first.pk}/")
        self.assertEqual(response.json()["id"], first.pk)
        response = self.client.delete("/api/timestamps/latest/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(list(Timestamp.objects.all()), [other])
