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

    def test_project_list(self):
        """Projects can be searched"""
        project = factories.ProjectFactory.create(title="Relaunch")
        factories.ProjectFactory.create(title="Other")
        self.client.force_login(project.owned_by)

        data = self.client.get("/api/projects/?q=relaunch").json()
        self.assertEqual([p["id"] for p in data], [project.pk])

    def test_project_and_offers(self):
        """Projects and their offers can be shown"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        factories.ServiceFactory.create(project=project, offer=offer, title="Design")
        self.client.force_login(project.owned_by)

        data = self.client.get(f"/api/projects/{project.pk}/").json()
        self.assertEqual(data["code"], project.code)
        self.assertTrue(data["url"].endswith(project.get_absolute_url()))

        data = self.client.get(f"/api/projects/{project.pk}/offers/").json()
        self.assertEqual([o["code"] for o in data], [offer.code])
        self.assertEqual(data[0]["services"][0]["title"], "Design")

        self.assertEqual(self.client.get("/api/projects/0/").status_code, 404)
        self.assertEqual(self.client.get("/api/projects/0/offers/").status_code, 404)

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
                ["body", "data", "services", 2],
                ["body", "data", "services", 3, "effort_rate"],
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
