import datetime as dt

from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.circles.models import Circle, Role
from workbench.circles.reporting import hours_by_circle


class CirclesTest(TestCase):
    def setUp(self):
        deactivate_all()

    def test_choices(self):
        """Role.objects.choices() works"""
        c = Circle.objects.create(name="B circle")
        r1 = c.roles.create(name="Role 1")
        c.roles.create(name="Role 2", is_removed=True)

        c = Circle.objects.create(name="A circle")
        r4 = c.roles.create(name="Role 1")
        r5 = c.roles.create(name="Role 2")
        r6 = c.roles.create(name="A circle", for_circle=True)

        self.assertEqual(
            Role.objects.choices(),
            [
                ("", "----------"),
                (
                    "A circle",
                    [
                        (r6.id, "For the circle [A circle]"),
                        (r4.id, "Role 1 [A circle]"),
                        (r5.id, "Role 2 [A circle]"),
                    ],
                ),
                (
                    "B circle",
                    [
                        (r1.id, "Role 1 [B circle]"),
                        # (r3.id, "(removed) Role 2 [B circle]"),
                    ],
                ),
            ],
        )

    def test_reporting(self):
        """Reporting hours per circle and role works"""
        r1 = Role.objects.create(name="Role 1", circle=Circle.objects.create(name="C1"))
        r2 = Role.objects.create(name="Role 2", circle=Circle.objects.create(name="C2"))
        Role.objects.create(name="Role 3", circle=r2.circle)
        Role.objects.create(name="Role 4", circle=Circle.objects.create(name="C4"))

        s1 = factories.ServiceFactory.create(role=r1)
        s2 = factories.ServiceFactory.create(role=r2)

        factories.LoggedHoursFactory.create(service=s1, hours=4)
        factories.LoggedHoursFactory.create(service=s2, hours=6)

        today = dt.date.today()
        circles = hours_by_circle(
            [dt.date(today.year, 1, 1), dt.date(today.year, 12, 31)]
        )["circles"]

        self.assertEqual(len(circles), 3)  # 2 circles and None
        self.assertEqual(circles[0]["total"], 0)
        self.assertEqual(circles[1]["total"], 4)
        self.assertEqual(circles[2]["total"], 6)
        # from pprint import pprint
        # pprint(hours_by_circle())

        self.client.force_login(s1.project.owned_by)
        response = self.client.get("/report/hours-by-circle/")
        self.assertEqual(response.status_code, 200)
        response = self.client.get(
            "/report/hours-by-circle/?users={}".format(s1.project.owned_by.id)
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "C1")
        self.assertContains(response, "C2")
        self.assertContains(response, "Role 1")
        self.assertContains(response, "Role 2")
        self.assertNotContains(response, "Role 3")
        self.assertNotContains(response, "Role 4")
        self.assertNotContains(response, "C4")

    def test_role_warning(self):
        """Users are warned when creating a service without selecting a role"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.post(
            project.urls["createservice"],
            {
                "title": "Consulting service",
                "effort_type": "Consulting",
                "effort_rate": "180",
                "allow_logging": True,
                # WarningsForm.ignore_warnings_id: "no-role-selected",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "No role selected.")

        r1 = Role.objects.create(name="Role 1", circle=Circle.objects.create(name="C1"))
        response = self.client.post(
            project.urls["createservice"],
            {
                "title": "Consulting service",
                "effort_type": "Consulting",
                "effort_rate": "180",
                "allow_logging": True,
                "role": r1.pk,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)
