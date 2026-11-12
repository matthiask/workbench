import datetime as dt
from decimal import Decimal
from unittest.mock import ANY

from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.invoices.models import Invoice
from workbench.offers.models import Offer, OfferHeading
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
        self.assertEqual(data["offers"][0]["project"]["id"], offer.project_id)
        self.assertEqual(data["offers"][0]["owned_by"], offer.owned_by.get_short_name())
        self.assertEqual(data["offers"][0]["services"][0]["title"], "Design")
        self.assertEqual(
            data["service_types"][0],
            {"id": ANY, "title": "consulting", "hourly_rate": "250.00"},
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

    def test_create_service_group(self):
        """Service groups may be created without services, with references"""
        project = factories.ProjectFactory.create()
        factories.PostalAddressFactory.create(person=project.contact)
        self.client.force_login(project.owned_by)
        url = f"/api/projects/{project.pk}/offers/"
        milestone = "https://github.com/example/repo/milestone/3"

        response = self.client.post(
            url, {"title": "Tranche 2"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["loc"], ["body", "data", "services"]
        )

        data = self.client.post(
            url,
            {
                "title": "Tranche 2",
                "status": "service_group",
                "external_reference": f" {milestone} \n",
            },
            content_type="application/json",
        ).json()
        offer = Offer.objects.get()
        self.assertEqual(data["id"], offer.pk)
        self.assertEqual(offer.status, Offer.SERVICE_GROUP)
        self.assertEqual(offer.external_reference, milestone)
        self.assertFalse(offer.services.exists())

        response = self.client.post(
            url,
            {"title": "Sent", "status": "accepted"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)

        # Their title and description can be changed, there's nothing else
        response = self.client.patch(
            f"/api/offers/{offer.pk}/",
            {"title": "Tranche 3", "description": "Later"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        offer.refresh_from_db()
        self.assertEqual((offer.title, offer.description), ("Tranche 3", "Later"))
        response = self.client.patch(
            f"/api/offers/{offer.pk}/",
            {"discount": 100},
            content_type="application/json",
        )
        self.assertContains(
            response,
            "Only the title, the description and the external reference"
            " of service groups can be changed.",
            status_code=409,
        )

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

    def test_headings(self):
        """Offers are created and replaced with headings between their
        services"""
        factories.service_types()
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)
        offer = self.offer(
            postal_address="A\nB\nC",
            headings=[
                {"title": "Concept phase", "description": "Ideas", "before": 0},
                {"title": "Operation", "before": 1},
                {"title": "Options", "before": 2},
            ],
        )
        url = f"/api/projects/{project.pk}/offers/"

        data = self.client.post(
            f"{url}?dry_run=true", offer, content_type="application/json"
        ).json()
        self.assertEqual(
            [(h["id"], h["title"], h["position"]) for h in data["headings"]],
            [
                (None, "Concept phase", 10),
                (None, "Operation", 30),
                (None, "Options", 50),
            ],
        )
        self.assertEqual([s["position"] for s in data["services"]], [20, 40, 60])
        self.assertFalse(OfferHeading.objects.exists())

        data = self.client.post(url, offer, content_type="application/json").json()
        instance = Offer.objects.get()
        self.assertEqual(
            [str(item) for item in instance.items()],
            ["Concept phase", "Concept", "Operation", "Hosting", "Options", "Extra"],
        )
        self.assertEqual(instance.headings.first().description, "Ideas")
        detail = self.client.get(f"/api/offers/{instance.code}/").json()
        self.assertEqual(len(detail["headings"]), 3)

        response = self.client.put(
            f"/api/offers/{instance.pk}/",
            self.offer(
                postal_address="A\nB\nC",
                headings=[{"title": "Everything", "before": 0}],
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            [str(item) for item in instance.items()],
            ["Everything", "Concept", "Hosting", "Extra"],
        )

        response = self.client.put(
            f"/api/offers/{instance.pk}/",
            self.offer(
                postal_address="A\nB\nC",
                headings=[{"title": "Too far", "before": 4}],
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["loc"],
            ["body", "data", "headings", 0, "before"],
        )

    def test_single_headings(self):
        """Headings are added in front of services or at the end, changed,
        moved and deleted one by one"""
        offer = factories.OfferFactory.create()
        first = factories.ServiceFactory.create(offer=offer, project=offer.project)
        second = factories.ServiceFactory.create(offer=offer, project=offer.project)
        other = factories.ServiceFactory.create(project=offer.project)
        self.client.force_login(offer.owned_by)

        def send(method, url, data=None, query=""):
            return getattr(self.client, method)(
                f"{url}{query}", data, content_type="application/json"
            )

        url = f"/api/offers/{offer.code}/headings/"
        response = send(
            "post", url, {"title": "Second", "before": second.pk}, "?dry_run=1"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["headings"][0]["id"], None)
        self.assertFalse(OfferHeading.objects.exists())

        response = send("post", url, {"title": "Second", "before": second.pk})
        heading = OfferHeading.objects.get()
        self.assertEqual(response.json()["headings"][0]["id"], heading.pk)
        self.assertEqual(offer.items(), [first, heading, second])

        response = send("post", url, {"title": "End", "description": "Last"})
        end = OfferHeading.objects.get(title="End")
        self.assertEqual(offer.items(), [first, heading, second, end])

        response = send("post", url, {"title": "X", "before": other.pk})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["loc"], ["body", "data", "before"]
        )

        url = f"/api/offers/headings/{heading.pk}/"
        response = send("patch", url, {"title": "First", "before": first.pk})
        self.assertEqual(response.status_code, 200, response.content)
        heading.refresh_from_db()
        self.assertEqual(heading.title, "First")
        self.assertEqual(offer.items(), [heading, first, second, end])

        response = send("patch", url, {"before": None})
        self.assertEqual(offer.items(), [first, second, end, heading])

        response = send("patch", url, {"title": ""})
        self.assertEqual(response.status_code, 422)

        response = send("delete", url, query="?dry_run=1")
        self.assertEqual(len(response.json()["headings"]), 1)
        self.assertTrue(OfferHeading.objects.filter(pk=heading.pk).exists())
        response = send("delete", url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(offer.items(), [first, second, end])

        Offer.objects.filter(pk=offer.pk).update(
            status=Offer.OFFERED,
            offered_on=dt.date.today(),
            valid_until=dt.date.today(),
        )
        response = send("delete", f"/api/offers/headings/{end.pk}/")
        self.assertEqual(response.status_code, 409)
        response = send("post", f"/api/offers/{offer.pk}/headings/", {"title": "X"})
        self.assertEqual(response.status_code, 409)

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
        discarded = factories.OfferFactory.create(status=Offer.DISCARDED)
        self.assertEqual(ids("?status=discarded"), [discarded.pk])
        discarded.delete()
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

    def test_dates(self):
        """Offers have their dates, closed_on is the date of the acceptance"""
        offer = factories.OfferFactory.create(
            status=Offer.ACCEPTED,
            offered_on=dt.date(2026, 9, 1),
            valid_until=dt.date(2026, 9, 30),
            closed_on=dt.date(2026, 9, 15),
            work_completed_on=dt.date(2026, 10, 31),
        )
        self.client.force_login(offer.owned_by)
        data = self.client.get(f"/api/offers/{offer.pk}/").json()
        self.assertEqual(
            {key: data[key] for key in data if key.endswith(("_on", "_until"))},
            {
                "offered_on": "2026-09-01",
                "valid_until": "2026-09-30",
                "closed_on": "2026-09-15",
                "work_completed_on": "2026-10-31",
            },
        )
        self.assertTrue(data["created_at"].startswith(str(offer.created_at.year)))


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

    def test_numbers_out_of_range(self):
        """Infinity, NaN and numbers too large for the database are rejected"""
        services = f"/api/projects/{self.project.pk}/offers/"
        for value in [float("inf"), float("nan"), 1e30, -1e30, 5e9, -5e9]:
            for method, url, data in [
                (
                    "post",
                    services,
                    {
                        "title": "X",
                        "services": [
                            {
                                "title": "Concept",
                                "service_type": "consulting",
                                "hours": value,
                            }
                        ],
                    },
                ),
                (
                    "post",
                    services,
                    {"title": "X", "services": [{"title": "Hosting", "cost": value}]},
                ),
                ("patch", self.url, {"discount": value}),
                ("patch", f"/api/services/{self.hosting.pk}/", {"cost": value}),
                (
                    "post",
                    "/api/services/",
                    {"offer": self.offer.pk, "title": "X", "hourly_rate": value},
                ),
            ]:
                response = getattr(self.client, method)(
                    url, data, content_type="application/json"
                )
                self.assertEqual(response.status_code, 422, (method, url, data))

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

        response = self.send("patch", data={"discount": 500})
        self.assertEqual(response.json()["total_excl_tax"], "2500.00")
        response = self.send("patch", data={"discount": None})
        self.assertEqual(response.json()["total_excl_tax"], "3000.00")

    def test_external_reference(self):
        """External references are changed for offers in any state and
        searched line by line"""
        self.offer.status = Offer.ACCEPTED
        self.offer.offered_on = dt.date.today()
        self.offer.valid_until = dt.date.today()
        self.offer.save()
        urls = "https://example.com/issues/1\n\n https://example.com/issues/12"
        response = self.send("patch", data={"external_reference": urls}, dry_run=True)
        self.assertEqual(response.status_code, 200, response.content)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.external_reference, "")

        response = self.send("patch", data={"external_reference": urls})
        self.assertEqual(
            response.json()["external_reference"],
            "https://example.com/issues/1\nhttps://example.com/issues/12",
        )
        other = factories.OfferFactory.create(
            external_reference="https://example.com/issues/12"
        )

        def ids(url):
            data = self.client.get("/api/offers/", {"external_reference": url}).json()
            return {o["id"] for o in data["items"]}

        self.assertEqual(ids("https://example.com/issues/1"), {self.offer.pk})
        self.assertEqual(
            ids("https://example.com/issues/12"), {self.offer.pk, other.pk}
        )
        self.assertEqual(ids("https://example.com/issues"), set())

        response = self.send("patch", data={"external_reference": None})
        self.assertEqual(response.json()["external_reference"], "")

    def test_external_reference_validation(self):
        """External references of offers are URLs separated by whitespace"""
        response = self.send(
            "patch",
            data={"external_reference": "https://example.com/1 https://example.com/2"},
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json()["external_reference"],
            "https://example.com/1\nhttps://example.com/2",
        )

        for data in [
            {"external_reference": "https://example.com/1 issue 2"},
            {"external_reference": "issue 2", "title": "Test"},
        ]:
            with self.subTest(data=data):
                response = self.send("patch", data=data)
                self.assertEqual(response.status_code, 422, response.content)
        self.offer.refresh_from_db()
        self.assertEqual(
            self.offer.external_reference,
            "https://example.com/1\nhttps://example.com/2",
        )

    def test_invoiced_services(self):
        """Offers with services which have been invoiced aren't replaced"""
        project = self.offer.project
        invoice = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            type=Invoice.SERVICES,
        )
        invoice.create_services_from_offer([self.hosting])

        response = self.client.put(
            f"/api/offers/{self.offer.pk}/",
            {"title": "Website", "services": [{"title": "Concept", "hours": 2}]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("invoiced", response.content.decode())
        self.assertEqual(self.offer.services.count(), 2)

    def test_not_in_preparation(self):
        """Only offers in preparation are changed"""
        self.offer.status = Offer.OFFERED
        self.offer.save()
        for method, path, data in [
            ("patch", "", {"title": "X", "external_reference": ""}),
            ("patch", "", {"title": "X"}),
        ]:
            with self.subTest(method=method, path=path):
                self.assertEqual(self.send(method, path, data).status_code, 409)

    def test_pdf(self):
        """Offers are downloaded as PDF like in the web interface"""
        response = self.client.get(f"/api/offers/{self.offer.pk}/pdf/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "application/pdf")
        self.assertTrue(b"".join(response).startswith(b"%PDF"))
        response = self.client.get(
            f"/api/offers/{self.offer.pk}/pdf/?signature_line=true"
        )
        self.assertEqual(response.status_code, 200)
