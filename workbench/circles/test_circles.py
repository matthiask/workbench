from django.test import TestCase

from workbench import factories
from workbench.circles.models import Circle, Role
from workbench.circles.reporting import logged_hours_by_circle


class CirclesTest(TestCase):
    def test_choices(self):
        c = Circle.objects.create(name="B circle")
        r1 = c.roles.create(name="Role 1")
        r3 = c.roles.create(name="Role 2", is_removed=True)

        c = Circle.objects.create(name="A circle")
        r4 = c.roles.create(name="Role 1")
        r5 = c.roles.create(name="Role 2")

        self.assertEqual(
            Role.objects.choices(),
            [
                ("", "----------"),
                ("A circle", [(r4.id, "Role 1"), (r5.id, "Role 2")]),
                ("B circle", [(r1.id, "Role 1"), (r3.id, "(entfernt) Role 2")]),
            ],
        )

    def test_reporting(self):
        r1 = Role.objects.create(name="Role 1", circle=Circle.objects.create(name="C1"))
        r2 = Role.objects.create(name="Role 2", circle=Circle.objects.create(name="C2"))

        s1 = factories.ServiceFactory.create(role=r1)
        s2 = factories.ServiceFactory.create(role=r2)

        factories.LoggedHoursFactory.create(service=s1, hours=4)
        factories.LoggedHoursFactory.create(service=s2, hours=6)

        circles = logged_hours_by_circle()

        self.assertEqual(len(circles), 3)  # 2 circles and None
        self.assertEqual(circles[0]["total"], 0)
        self.assertEqual(circles[1]["total"], 4)
        self.assertEqual(circles[2]["total"], 6)
        # from pprint import pprint
        # pprint(logged_hours_by_circle())

        self.client.force_login(s1.project.owned_by)
        response = self.client.get("/report/logged-hours-by-circle/")
        self.assertEqual(response.status_code, 200)
