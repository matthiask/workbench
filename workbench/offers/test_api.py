import datetime as dt
from decimal import Decimal

from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.offers.models import Offer
from workbench.projects.models import Service


class OffersAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def offer(self, **kwargs):
        return {
            "title": "Relaunch",
            "description": "Everything new",
            "services": [
                {
                    "title": "Concept",
                    "service_type": "consulting",
                    "hours": 10,
                },
                {
                    "title": "Hosting",
                    "cost": 500,
                    "third_party_costs": 300,
                },
                {
                    "title": "Extra",
                    "service_type": "production",
                    "hours": 4,
                    "hourly_rate": 100,
                    "is_optional": True,
                },
            ],
        } | kwargs

    def test_context(self):
        """The context contains the project, offers and service types"""
        factories.service_types()
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        factories.ServiceFactory.create(project=project, offer=offer, title="Design")

        url = f"/api/projects/{project.pk}/offers/context/"
        self.assertEqual(self.client.get(url).status_code, 401)

        self.client.force_login(project.owned_by)
        data = self.client.get(url).json()
        self.assertEqual(data["project"]["code"], project.code)
        self.assertEqual(data["offers"][0]["code"], offer.code)
        self.assertEqual(data["offers"][0]["services"][0]["title"], "Design")
        self.assertEqual(
            data["service_types"][0], {"title": "consulting", "hourly_rate": "250.00"}
        )
        self.assertNotIn("@", str(data))

        service = data["import_schema"]["$defs"]["ServiceIn"]["properties"]
        self.assertEqual(
            service["service_type"]["anyOf"][0]["enum"],
            ["consulting", "production", "administration"],
        )

    def test_project_and_offers(self):
        """Projects and their offers can be shown"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        factories.ServiceFactory.create(project=project, offer=offer, title="Design")
        self.client.force_login(project.owned_by)

        data = self.client.get(f"/api/projects/{project.pk}/").json()
        self.assertEqual(data["code"], project.code)
        self.assertEqual(data["url"], f"http://testserver{project.get_absolute_url()}")

        data = self.client.get(f"/api/offers/?project={project.pk}").json()["items"]
        self.assertEqual([o["code"] for o in data], [offer.code])
        self.assertEqual(data[0]["services"][0]["title"], "Design")
        self.assertEqual(data[0]["url"], f"http://testserver{offer.get_absolute_url()}")

        self.assertEqual(self.client.get("/api/projects/0/").status_code, 404)

    def test_create(self):
        """Creating adds an offer in preparation with its services"""
        factories.service_types()
        project = factories.ProjectFactory.create()
        factories.PostalAddressFactory.create(person=project.contact)
        self.client.force_login(project.owned_by)
        url = f"/api/projects/{project.pk}/offers/"

        response = self.client.post(
            f"{url}?dry_run=true", self.offer(), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["id"])
        self.assertEqual(data["subtotal"], "3000.00")
        self.assertFalse(Offer.objects.exists())
        self.assertFalse(Service.objects.exists())

        data = self.client.post(
            url, self.offer(), content_type="application/json"
        ).json()
        offer = Offer.objects.get()
        self.assertEqual(data["id"], offer.pk)
        self.assertEqual(data["code"], offer.code)
        self.assertEqual(offer.status, Offer.IN_PREPARATION)
        self.assertEqual(offer.owned_by, project.owned_by)
        self.assertEqual(offer.subtotal, Decimal("3000.00"))
        self.assertNotEqual(offer.postal_address, "")
        self.assertEqual(
            [
                (s.title, s.effort_type, s.effort_rate, s.service_cost)
                for s in offer.services.all()
            ],
            [
                ("Concept", "consulting", Decimal("250.00"), Decimal("2500.00")),
                ("Hosting", "", None, Decimal("500.00")),
                ("Extra", "production", Decimal("100.00"), Decimal("400.00")),
            ],
        )

    def test_create_errors(self):
        """Nothing is saved when anything is invalid"""
        factories.service_types()
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.post(
            f"/api/projects/{project.pk}/offers/",
            self.offer(
                services=[
                    {"title": "Unknown", "service_type": "magic", "hours": 1},
                    {"title": "No type", "hours": 1},
                    {"title": "Nothing"},
                    {"title": "No rate", "effort_type": "Design", "hours": 1},
                ]
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"] for error in response.json()["detail"]],
            [
                ["body", "data", "postal_address"],
                ["body", "data", "services", 0, "service_type"],
                ["body", "data", "services", 1, "hours"],
                ["body", "data", "services", 3, "hourly_rate"],
            ],
        )
        self.assertFalse(Offer.objects.exists())

    def test_effort_type(self):
        """Service types only suggest the effort type and the hourly rate"""
        factories.service_types()
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        data = self.client.post(
            f"/api/projects/{project.pk}/offers/",
            self.offer(
                postal_address="A\nB\nC",
                services=[
                    {
                        "title": "Design",
                        "effort_type": "Design",
                        "hourly_rate": 200,
                        "hours": 3,
                    },
                    {
                        "title": "Workshop",
                        "service_type": "consulting",
                        "effort_type": "Workshop",
                        "hours": 2,
                    },
                ],
            ),
            content_type="application/json",
        ).json()
        self.assertEqual(
            [(s["effort_type"], s["effort_rate"]) for s in data["services"]],
            [("Design", "200.00"), ("Workshop", "250.00")],
        )

    def test_flat_rate(self):
        """Projects with a flat rate use it for all services"""
        factories.service_types()
        project = factories.ProjectFactory.create(flat_rate=160)
        self.client.force_login(project.owned_by)

        data = self.client.post(
            f"/api/projects/{project.pk}/offers/",
            self.offer(postal_address="A\nB\nC"),
            content_type="application/json",
        ).json()
        self.assertEqual([s["effort_rate"] for s in data["services"]], ["160.00"] * 3)

    def test_replace(self):
        """Offers in preparation can be replaced"""
        factories.service_types()
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)
        data = self.client.post(
            f"/api/projects/{project.pk}/offers/",
            self.offer(postal_address="A\nB\nC"),
            content_type="application/json",
        ).json()
        url = f"/api/offers/{data['id']}/"

        replacement = self.offer(
            title="Smaller relaunch",
            services=[{"title": "Concept", "service_type": "consulting", "hours": 2}],
        )
        response = self.client.put(url, replacement, content_type="application/json")
        self.assertEqual(response.json()["subtotal"], "500.00")
        offer = Offer.objects.get()
        self.assertEqual(offer.title, "Smaller relaunch")
        self.assertEqual(offer.postal_address, "A\nB\nC")
        self.assertEqual([s.title for s in offer.services.all()], ["Concept"])
        self.assertEqual(self.client.get(url).json()["subtotal"], "500.00")

        factories.LoggedHoursFactory.create(service=offer.services.get())
        response = self.client.put(url, replacement, content_type="application/json")
        self.assertEqual(response.status_code, 422)

        offer.status = Offer.OFFERED
        offer.offered_on = offer.valid_until = offer.created_at.date()
        offer.save()
        response = self.client.put(url, replacement, content_type="application/json")
        self.assertEqual(response.status_code, 409)

    def test_search(self):
        """Offers can be searched and filtered"""
        user = factories.UserFactory.create(_short_name="ab")
        relaunch = factories.OfferFactory.create(
            title="Website relaunch", owned_by=user
        )
        other = factories.OfferFactory.create(title="Hosting", status=Offer.DECLINED)
        self.client.force_login(user)

        def ids(query=""):
            return [
                o["id"] for o in self.client.get(f"/api/offers/{query}").json()["items"]
            ]

        self.assertEqual(ids(), [other.pk, relaunch.pk])
        self.assertEqual(ids("?q=relaunch"), [relaunch.pk])
        self.assertEqual(ids(f"?q={other.project.code}"), [other.pk])
        self.assertEqual(ids("?status=declined"), [other.pk])
        self.assertEqual(ids("?owned_by=AB"), [relaunch.pk])
        self.assertEqual(ids(f"?project={other.project_id}"), [other.pk])
        self.assertEqual(
            ids(f"?customer={relaunch.project.customer_id}"), [relaunch.pk]
        )
        self.assertEqual(self.client.get("/api/offers/?status=nope").status_code, 422)

        relaunch.offered_on = dt.date(2026, 9, 10)
        relaunch.save()
        self.assertEqual(ids("?period=2026-09"), [relaunch.pk])
        self.assertEqual(ids("?until=2026-08-31"), [])


class OfferServicesAPITest(TestCase):
    """Editing single services of offers in preparation"""

    def tearDown(self):
        deactivate_all()

    def setUp(self):
        factories.service_types()
        self.project = factories.ProjectFactory.create()
        factories.PostalAddressFactory.create(person=self.project.contact)
        self.client.force_login(self.project.owned_by)
        response = self.client.post(
            f"/api/projects/{self.project.pk}/offers/",
            {
                "title": "Relaunch",
                "services": [
                    {"title": "Concept", "service_type": "consulting", "hours": 10},
                    {"title": "Hosting", "cost": 500},
                ],
            },
            content_type="application/json",
        )
        self.offer = Offer.objects.get(pk=response.json()["id"])
        self.concept, self.hosting = self.offer.services.all()
        self.url = f"/api/offers/{self.offer.pk}/"

    def send(self, method, path="", data=None, **params):
        query = "?dry_run=true" if params.get("dry_run") else ""
        return getattr(self.client, method)(
            f"{self.url}{path}{query}", data, content_type="application/json"
        )

    def test_output(self):
        """Services have their position and their service type"""
        data = self.client.get(self.url).json()
        self.assertEqual(
            [(s["position"], s["service_type"]) for s in data["services"]],
            [(10, "consulting"), (20, None)],
        )
        self.concept.effort_rate = 200
        self.concept.save()
        data = self.client.get(self.url).json()
        self.assertIsNone(data["services"][0]["service_type"])

    def test_update_offer(self):
        """The title, the description and the postal address are changed
        separately"""
        response = self.send("patch", data={"title": "Website"}, dry_run=True)
        self.assertEqual(response.json()["title"], "Website")
        self.assertEqual(response.json()["id"], self.offer.pk)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.title, "Relaunch")

        response = self.send("patch", data={"description": "New"})
        self.assertEqual(response.status_code, 200, response.content)
        self.offer.refresh_from_db()
        self.assertEqual(
            (self.offer.title, self.offer.description), ("Relaunch", "New")
        )

        response = self.send("patch", data={"title": ""})
        self.assertEqual(response.status_code, 422)

    def test_add(self):
        """Services are added at the end or after another service"""
        service = {"title": "Design", "service_type": "production", "hours": 5}
        response = self.send("post", "services/", service, dry_run=True)
        data = response.json()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([s["title"] for s in data["services"]][-1], "Design")
        self.assertIsNone(data["services"][-1]["id"])
        self.assertEqual(data["services"][0]["id"], self.concept.pk)
        self.assertEqual(data["total_excl_tax"], "3900.00")
        self.assertEqual(self.offer.services.count(), 2)

        response = self.send("post", "services/", service | {"after": self.concept.pk})
        data = response.json()
        self.assertEqual(
            [(s["title"], s["position"]) for s in data["services"]],
            [("Concept", 10), ("Design", 20), ("Hosting", 30)],
        )
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.total_excl_tax, Decimal("3900.00"))

        response = self.send("post", "services/", service | {"after": 0})
        self.assertEqual(response.status_code, 422)
        # Services without hours and costs are allowed like in the web
        # interface, e.g. to estimate them later
        response = self.send("post", "services/", {"title": "Nothing"}, dry_run=True)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json()["warnings"],
            [
                {
                    "loc": ["body", "data"],
                    "msg": "Nothing: Neither hours nor a cost have been given yet.",
                }
            ],
        )
        self.assertEqual(self.client.get(self.url).json()["warnings"], [])

    def test_update(self):
        """Only the given fields change, null clears values"""
        path = f"services/{self.concept.pk}/"
        response = self.send("patch", path, {"hours": 12}, dry_run=True)
        self.assertEqual(response.json()["total_excl_tax"], "3500.00")
        self.concept.refresh_from_db()
        self.assertEqual(self.concept.effort_hours, 10)

        # Service types fill in the effort type and the rate...
        response = self.send("patch", path, {"service_type": "production"})
        self.concept.refresh_from_db()
        self.assertEqual(
            (self.concept.title, self.concept.effort_type, self.concept.effort_rate),
            ("Concept", "production", 180),
        )
        # ... unless they are given too
        self.send("patch", path, {"service_type": "consulting", "hourly_rate": 200})
        self.concept.refresh_from_db()
        self.assertEqual(
            (self.concept.effort_type, self.concept.effort_rate), ("consulting", 200)
        )

        path = f"services/{self.hosting.pk}/"
        response = self.send("patch", path, {"cost": None}, dry_run=True)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.json()["warnings"]), 1)
        response = self.send(
            "patch", path, {"cost": None, "service_type": "consulting", "hours": 1}
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.hosting.refresh_from_db()
        self.assertIsNone(self.hosting.cost)
        self.assertEqual(self.hosting.service_cost, 250)

        response = self.send(
            "patch", path, {"hours": 2, "effort_type": None, "hourly_rate": None}
        )
        self.assertEqual(
            [e["loc"] for e in response.json()["detail"]], [["body", "data", "hours"]]
        )

        # Logged hours don't prevent changes, like in the web interface
        factories.LoggedHoursFactory.create(service=self.hosting)
        response = self.send("patch", path, {"description": "Servers"})
        self.assertEqual(response.status_code, 200, response.content)

    def test_flat_rate(self):
        """Flat rates win"""
        self.project.flat_rate = 160
        self.project.save()
        response = self.send(
            "patch", f"services/{self.concept.pk}/", {"hourly_rate": 300}
        )
        self.assertEqual(response.json()["services"][0]["effort_rate"], "160.00")

    def test_delete(self):
        """Services without logbook entries can be deleted, but not the last
        one"""
        response = self.send("delete", f"services/{self.hosting.pk}/", dry_run=True)
        self.assertEqual(response.json()["total_excl_tax"], "2500.00")
        self.assertEqual(self.offer.services.count(), 2)

        factories.LoggedHoursFactory.create(service=self.hosting)
        response = self.send("delete", f"services/{self.hosting.pk}/")
        self.assertEqual(response.status_code, 422)
        self.assertIn("logged", response.content.decode())

        response = self.send("delete", f"services/{self.concept.pk}/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([s.pk for s in self.offer.services.all()], [self.hosting.pk])
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.total_excl_tax, Decimal("500.00"))

        response = self.send("delete", f"services/{self.hosting.pk}/")
        self.assertEqual(response.status_code, 422)
        self.assertIn("last service", response.content.decode())

    def test_reorder(self):
        """Services are reordered by listing all their IDs"""
        order = {"services": [self.hosting.pk, self.concept.pk]}
        response = self.send("post", "services/reorder/", order)
        self.assertEqual(
            [s["title"] for s in response.json()["services"]], ["Hosting", "Concept"]
        )
        self.assertEqual(
            [s.pk for s in self.offer.services.all()],
            [self.hosting.pk, self.concept.pk],
        )
        for services in [[self.hosting.pk], [self.hosting.pk] * 2, [1, 2]]:
            response = self.send("post", "services/reorder/", {"services": services})
            self.assertEqual(response.status_code, 422)

    def test_not_in_preparation(self):
        """Only offers in preparation are changed, only their own services"""
        other = factories.ServiceFactory.create(project=self.project)
        response = self.send("patch", f"services/{other.pk}/", {"hours": 1})
        self.assertEqual(response.status_code, 404)
        response = self.send("delete", f"services/{other.pk}/")
        self.assertEqual(response.status_code, 404)

        self.offer.status = Offer.OFFERED
        self.offer.save()
        for method, path, data in [
            ("patch", "", {"title": "X"}),
            ("post", "services/", {"title": "X", "cost": 1}),
            ("patch", f"services/{self.concept.pk}/", {"hours": 1}),
            ("delete", f"services/{self.concept.pk}/", None),
            ("post", "services/reorder/", {"services": []}),
        ]:
            with self.subTest(method=method, path=path):
                self.assertEqual(self.send(method, path, data).status_code, 409)
