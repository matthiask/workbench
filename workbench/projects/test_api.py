import datetime as dt
from decimal import Decimal

from django.test import TestCase
from django.test.utils import override_settings
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.invoices.models import Invoice
from workbench.offers.models import Offer, OfferHeading
from workbench.projects.models import Campaign, InternalType, Project, Service
from workbench.reporting.models import FreezeDate
from workbench.tools.testing import messages
from workbench.tools.validation import in_days, monday


class ProjectsAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def test_project_list(self):
        """Projects can be searched"""
        project = factories.ProjectFactory.create(
            title="Relaunch",
            owned_by=factories.UserFactory.create(_short_name="ab"),
        )
        other = factories.ProjectFactory.create(title="Other")
        self.client.force_login(project.owned_by)

        def ids(query=""):
            return {
                p["id"]
                for p in self.client.get(f"/api/projects/{query}").json()["items"]
            }

        self.assertEqual(ids("?q=relaunch"), {project.pk})
        self.assertEqual(ids(f"?customer={other.customer_id}"), {other.pk})
        self.assertEqual(ids("?owned_by=AB"), {project.pk})

        data = self.client.get(f"/api/projects/{project.pk}/").json()
        self.assertEqual(
            data["customer"],
            {
                "id": project.customer_id,
                "url": f"http://testserver{project.customer.get_absolute_url()}",
                "name": project.customer.name,
                "is_archived": False,
            },
        )
        item = next(
            p
            for p in self.client.get("/api/projects/?q=relaunch").json()["items"]
            if p["id"] == project.pk
        )
        self.assertEqual(item["contact"]["id"], project.contact_id)
        self.assertEqual(item["contact"]["full_name"], project.contact.full_name)
        self.assertEqual(item["created_at"][:10], project.created_at.date().isoformat())

    def test_stats(self):
        """Statistics of the selected projects"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(
            project=project,
            status=Offer.ACCEPTED,
            offered_on=dt.date.today(),
            valid_until=dt.date.today(),
        )
        service = factories.ServiceFactory.create(
            project=project,
            offer=offer,
            title="Design",
            effort_type="Design",
            effort_hours=10,
            effort_rate=200,
        )
        user = factories.UserFactory.create(_short_name="ab")
        factories.LoggedHoursFactory.create(service=service, rendered_by=user, hours=3)
        factories.LoggedHoursFactory.create(service=service, rendered_by=user, hours=2)
        factories.PlannedWorkFactory.create(
            project=project, user=user, weeks=[monday()], planned_hours=8
        )
        factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            status=Invoice.SENT,
            subtotal=600,
        )
        factories.InvoiceFactory.create(project=project, customer=project.customer)
        closed = factories.ProjectFactory.create(closed_on=dt.date(2026, 6, 1))
        factories.ProjectFactory.create(closed_on=dt.date(2025, 6, 1))
        self.client.force_login(project.owned_by)

        self.assertEqual(self.client.get("/api/projects/stats/").status_code, 400)

        data = self.client.get(f"/api/projects/stats/?ids={project.pk}").json()
        self.assertEqual(len(data), 1)
        stats = data[0]
        self.assertEqual(stats["project"]["id"], project.pk)
        self.assertEqual(
            stats["hours"],
            {
                "offered": "10.0",
                "logged": "5.0",
                "logged_rate_undefined": "0.0",
                "planned": "8.0",
            },
        )
        self.assertEqual(stats["amounts"]["sold"], "2000.00")
        self.assertEqual(stats["amounts"]["invoiced"], "600.00")
        self.assertEqual(stats["amounts"]["effort_cost"], "1000.00")
        self.assertEqual(stats["amounts"]["not_invoiced"], "400.00")
        self.assertEqual(stats["gross_margin"]["gross_margin"], "2000.00")
        self.assertEqual(stats["services"][0]["effort_rate"], "200.00")
        self.assertEqual(
            stats["logged_hours"],
            [{"service": service.pk, "user": "ab", "hours": "5.0"}],
        )
        self.assertEqual(
            stats["planned_hours"],
            [{"user": "ab", "planned_hours": "8.0", "is_provisional": False}],
        )
        self.assertEqual([i["total_excl_tax"] for i in stats["invoices"]], ["600.00"])

        data = self.client.get(
            "/api/projects/stats/?open=true&closed_since=2026-01-01"
        ).json()
        self.assertEqual([s["project"]["id"] for s in data], [project.pk, closed.pk])

        data = self.client.get(
            f"/api/projects/stats/?ids={project.pk}&ids={closed.pk}"
        ).json()
        self.assertEqual(len(data), 2)
        self.assertEqual(Decimal(data[1]["hours"]["logged"]), 0)

    def test_no_messages_for_the_web_interface(self):
        """Messages added during API requests don't show up later in the web
        interface"""
        project = factories.ProjectFactory.create()
        factories.OfferFactory.create(project=project)
        self.client.force_login(project.owned_by)
        response = self.client.patch(
            f"/api/projects/{project.pk}/?dry_run=true",
            {"closed_on": dt.date.today().isoformat()},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        response = self.client.get(project.urls["detail"])
        self.assertEqual(messages(response), [])

    def test_create(self):
        """Projects are validated like in the web interface"""
        user = factories.UserFactory.create()
        other = factories.UserFactory.create(_short_name="ot")
        customer = factories.OrganizationFactory.create()
        contact = factories.PersonFactory.create(organization=customer)
        self.client.force_login(user)

        data = {
            "title": "Relaunch",
            "customer": customer.pk,
            "contact": contact.pk,
        }
        response = self.client.post(
            "/api/projects/?dry_run=true", data, content_type="application/json"
        )
        self.assertEqual(response.json()["id"], None)
        self.assertFalse(Project.objects.exists())

        response = self.client.post(
            "/api/projects/", data, content_type="application/json"
        )
        project = Project.objects.get()
        self.assertEqual(response.json()["id"], project.pk)
        self.assertEqual(project.owned_by, user)
        self.assertEqual(project.contact, contact)
        self.assertEqual(project.type, Project.ORDER)

        response = self.client.post(
            "/api/projects/",
            data | {"owned_by": "OT", "type": "maintenance"},
            content_type="application/json",
        )
        project = Project.objects.get(pk=response.json()["id"])
        self.assertEqual(project.owned_by, other)
        self.assertEqual(project.type, Project.MAINTENANCE)

        # Warnings of the web interface are errors
        response = self.client.post(
            "/api/projects/",
            data | {"contact": None},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"],
            [
                {
                    "loc": ["body", "data"],
                    "msg": "No contact selected.",
                    "code": "no-contact",
                }
            ],
        )

        response = self.client.post(
            "/api/projects/",
            data | {"customer": 0, "owned_by": "nobody"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [e["loc"] for e in response.json()["detail"]],
            [["body", "data", "owned_by"]],
        )

        response = self.client.post(
            "/api/projects/",
            data | {"customer": 0},
            content_type="application/json",
        )
        self.assertEqual(
            [e["loc"] for e in response.json()["detail"]],
            [["body", "data", "customer"]],
        )

    def test_create_customer_from_contact(self):
        """The customer defaults to the contact's organization"""
        user = factories.UserFactory.create()
        contact = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )
        self.client.force_login(user)

        response = self.client.post(
            "/api/projects/",
            {"title": "Relaunch", "contact": contact.pk},
            content_type="application/json",
        )
        project = Project.objects.get(pk=response.json()["id"])
        self.assertEqual(project.customer, contact.organization)

        loner = factories.PersonFactory.create(organization=None)
        for data in [{"contact": loner.pk}, {}]:
            with self.subTest(data=data):
                response = self.client.post(
                    "/api/projects/",
                    {"title": "Relaunch"} | data,
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 422)
                self.assertEqual(
                    [e["loc"] for e in response.json()["detail"]],
                    [["body", "data", "customer"]],
                )

    def test_ignore_warnings(self):
        """Warnings of the web interface are errors unless ignored by their
        code"""
        project = factories.ProjectFactory.create(contact=None)
        self.client.force_login(project.owned_by)
        url = f"/api/projects/{project.pk}/"
        data = {"closed_on": in_days(-10).isoformat()}

        response = self.client.patch(url, data, content_type="application/json")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"],
            [
                {
                    "loc": ["body", "data"],
                    "msg": "No contact selected.",
                    "code": "no-contact",
                }
            ],
        )

        response = self.client.patch(
            f"{url}?ignore_warnings=no-contact", data, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        project.refresh_from_db()
        self.assertEqual(project.closed_on, in_days(-10))

        # Ignoring one warning doesn't ignore the others
        FreezeDate.objects.create(up_to=in_days(-5))
        response = self.client.patch(
            f"{url}?ignore_warnings=no-contact",
            {"closed_on": None},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["code"] for error in response.json()["detail"]],
            ["reopen-frozen-project"],
        )
        response = self.client.patch(
            f"{url}?ignore_warnings=no-contact&ignore_warnings=reopen-frozen-project",
            {"closed_on": None},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        response = self.client.post(
            "/api/projects/?ignore_warnings=no-contact",
            {"title": "Without contact", "customer": project.customer_id},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)

    @override_settings(FEATURES={FEATURES.CAMPAIGNS: F.ALWAYS})
    def test_campaigns(self):
        """Campaigns with open projects are listed, the closed ones too if
        wanted; projects have their campaign"""
        user = factories.UserFactory.create(_short_name="ab")
        campaign = factories.CampaignFactory.create(title="Relaunch", owned_by=user)
        project = factories.ProjectFactory.create(campaign=campaign)
        old = factories.CampaignFactory.create(title="Old")
        factories.ProjectFactory.create(campaign=old, closed_on=in_days(-10))
        self.client.force_login(user)

        def titles(**params):
            return [
                row["title"]
                for row in self.client.get("/api/campaigns/", params).json()["items"]
            ]

        self.assertEqual(titles(), ["Relaunch"])
        self.assertEqual(titles(include_closed=True), ["Old", "Relaunch"])
        self.assertEqual(titles(q="relaunch", owned_by="ab"), ["Relaunch"])

        data = self.client.get(f"/api/projects/{project.pk}/").json()
        self.assertEqual(data["campaign"]["id"], campaign.pk)

    @override_settings(FEATURES={FEATURES.CAMPAIGNS: F.ALWAYS})
    def test_campaign_create(self):
        """Campaigns are created through the web form, owned by the current
        user by default"""
        user = factories.UserFactory.create(_short_name="ab")
        other = factories.UserFactory.create(_short_name="cd")
        inactive = factories.UserFactory.create(_short_name="ef", is_active=False)
        organization = factories.OrganizationFactory.create()
        self.client.force_login(user)

        response = self.client.post(
            "/api/campaigns/?dry_run=1",
            {"title": "Relaunch", "customer": organization.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["id"], None)
        self.assertEqual(data["title"], "Relaunch")
        self.assertEqual(data["owned_by"], "ab")
        self.assertEqual(Campaign.objects.count(), 0)

        response = self.client.post(
            "/api/campaigns/",
            {
                "title": "Relaunch",
                "description": "All sites",
                "customer": organization.pk,
                "owned_by": "CD",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        campaign = Campaign.objects.get()
        self.assertEqual(response.json()["id"], campaign.pk)
        self.assertEqual(campaign.owned_by, other)
        self.assertEqual(campaign.description, "All sites")

        response = self.client.post(
            "/api/campaigns/",
            {
                "title": "Relaunch",
                "customer": organization.pk,
                "owned_by": inactive.get_short_name(),
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"] for error in response.json()["detail"]],
            [["body", "data", "owned_by"]],
        )

        response = self.client.post(
            "/api/campaigns/",
            {"title": "Relaunch", "customer": 0},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"] for error in response.json()["detail"]],
            [["body", "data", "customer"]],
        )

    @override_settings(FEATURES={FEATURES.CAMPAIGNS: F.ALWAYS})
    def test_campaign_update(self):
        """Campaigns are changed through the web form, only the given
        fields"""
        user = factories.UserFactory.create(_short_name="ab")
        campaign = factories.CampaignFactory.create(
            title="Relaunch", description="All sites"
        )
        organization = factories.OrganizationFactory.create()
        self.client.force_login(user)
        url = f"/api/campaigns/{campaign.pk}/"

        response = self.client.patch(
            f"{url}?dry_run=1", {"title": "Rebrand"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["title"], "Rebrand")
        campaign.refresh_from_db()
        self.assertEqual(campaign.title, "Relaunch")

        response = self.client.patch(
            url,
            {"owned_by": "ab", "customer": organization.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["owned_by"], "ab")
        self.assertEqual(data["customer"]["id"], organization.pk)
        campaign.refresh_from_db()
        self.assertEqual(campaign.title, "Relaunch")
        self.assertEqual(campaign.description, "All sites")
        self.assertEqual(campaign.owned_by, user)

        response = self.client.patch(
            url, {"title": None}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"] for error in response.json()["detail"]],
            [["body", "data", "title"]],
        )

        response = self.client.patch(
            url, {"owned_by": "nobody"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422)

        response = self.client.patch(
            url, {"code": "x"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422)

        self.assertEqual(
            self.client.patch(
                "/api/campaigns/0/", {"title": "x"}, content_type="application/json"
            ).status_code,
            404,
        )

    @override_settings(FEATURES={FEATURES.CAMPAIGNS: F.ALWAYS})
    def test_campaign_delete(self):
        """Deleting a campaign releases its projects, which is a warning"""
        user = factories.UserFactory.create()
        campaign = factories.CampaignFactory.create(title="Relaunch")
        project = factories.ProjectFactory.create(campaign=campaign)
        self.client.force_login(user)
        url = f"/api/campaigns/{campaign.pk}/"

        response = self.client.delete(url)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["code"] for error in response.json()["detail"]],
            ["release-projects"],
        )

        response = self.client.delete(
            f"{url}?ignore_warnings=release-projects&dry_run=1"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["id"], campaign.pk)
        self.assertTrue(Campaign.objects.filter(pk=campaign.pk).exists())

        response = self.client.delete(f"{url}?ignore_warnings=release-projects")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["title"], "Relaunch")
        self.assertFalse(Campaign.objects.filter(pk=campaign.pk).exists())
        project.refresh_from_db()
        self.assertIsNone(project.campaign)

        # Without projects there is nothing to confirm
        empty = factories.CampaignFactory.create()
        response = self.client.delete(f"/api/campaigns/{empty.pk}/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(Campaign.objects.filter(pk=empty.pk).exists())
        self.assertEqual(self.client.delete(url).status_code, 404)

    @override_settings(FEATURES={FEATURES.CAMPAIGNS: F.NEVER})
    def test_campaign_writes_require_the_feature(self):
        """Without the campaigns feature, campaigns can't be changed"""
        campaign = factories.CampaignFactory.create()
        self.client.force_login(campaign.owned_by)
        url = f"/api/campaigns/{campaign.pk}/"
        response = self.client.post(
            "/api/campaigns/",
            {"title": "x", "customer": campaign.customer_id},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.patch(
            url, {"title": "x"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.assertTrue(Campaign.objects.filter(pk=campaign.pk).exists())

    def test_service_types(self):
        """Service types are listed with the titles services take"""
        service_types = factories.service_types()
        self.client.force_login(factories.UserFactory.create())
        data = self.client.get("/api/service-types/").json()
        self.assertIn(
            {
                "id": service_types.consulting.pk,
                "title": service_types.consulting.title,
                "hourly_rate": "250.00",
            },
            data,
        )

    def test_internal_types(self):
        """Internal types are listed in their order"""
        outreach = InternalType.objects.create(
            name="Outreach", percentage=50, is_outreach=True, ordering=20
        )
        administration = InternalType.objects.create(
            name="Administration",
            description="Bookkeeping",
            percentage=100,
            ordering=10,
        )
        self.client.force_login(factories.UserFactory.create())

        response = self.client.get("/api/projects/internal-types/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["items"],
            [
                {
                    "id": administration.pk,
                    "name": "Administration",
                    "description": "Bookkeeping",
                    "percentage": "100.00",
                    "is_outreach": False,
                },
                {
                    "id": outreach.pk,
                    "name": "Outreach",
                    "description": "",
                    "percentage": "50.00",
                    "is_outreach": True,
                },
            ],
        )

    @override_settings(FEATURES={FEATURES.INTERNAL_TYPES: F.ALWAYS})
    def test_internal_type(self):
        """Internal projects get their internal type by name"""
        InternalType.objects.create(name="Administration", percentage=100)
        contact = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )
        self.client.force_login(factories.UserFactory.create())
        data = {"title": "Bookkeeping", "contact": contact.pk, "type": "internal"}

        response = self.client.post(
            "/api/projects/", data, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["loc"], ["body", "data", "internal_type"]
        )

        response = self.client.post(
            "/api/projects/",
            data | {"internal_type": "Unknown"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("Administration", response.json()["detail"][0]["msg"])

        # By ID too
        administration = InternalType.objects.get()
        response = self.client.post(
            "/api/projects/?dry_run=true",
            data | {"internal_type": str(administration.pk)},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["internal_type"], "Administration")

        response = self.client.post(
            "/api/projects/",
            data | {"internal_type": "administration"},
            content_type="application/json",
        )
        self.assertEqual(response.json()["internal_type"], "Administration")
        project = Project.objects.get(pk=response.json()["id"])

        # Projects which aren't internal anymore lose their internal type
        response = self.client.patch(
            f"/api/projects/{project.pk}/",
            {"type": "order"},
            content_type="application/json",
        )
        self.assertEqual(response.json()["internal_type"], None)

        response = self.client.patch(
            f"/api/projects/{project.pk}/",
            {"type": "internal", "internal_type": "Administration"},
            content_type="application/json",
        )
        self.assertEqual(response.json()["internal_type"], "Administration")

    def test_services(self):
        """Services with their logged hours and costs"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        design = factories.ServiceFactory.create(
            project=project,
            offer=offer,
            title="Design",
            effort_type="Design",
            effort_hours=10,
            effort_rate=200,
        )
        hosting = factories.ServiceFactory.create(
            project=project, title="Hosting", cost=500
        )
        factories.LoggedHoursFactory.create(service=design, hours=3)
        factories.LoggedHoursFactory.create(service=design, hours=2)
        factories.LoggedCostFactory.create(service=hosting, cost=100)
        factories.ServiceFactory.create(title="Other project")
        self.client.force_login(project.owned_by)

        data = self.client.get(f"/api/services/?project={project.pk}").json()["items"]
        self.assertEqual(
            [
                (s["title"], s["offer"], s["service_hours"], s["logged_hours"])
                for s in data
            ],
            [("Design", offer.code, "10.0", "5.0"), ("Hosting", None, "0.0", "0.0")],
        )
        self.assertEqual(data[1]["cost"], "500.00")
        self.assertEqual(data[1]["logged_cost"], "100.00")
        self.assertEqual(data[0]["effort_rate"], "200.00")

        data = self.client.get(f"/api/services/?offer={offer.pk}").json()["items"]
        self.assertEqual([s["id"] for s in data], [design.pk])
        data = self.client.get("/api/services/?q=hosting").json()["items"]
        self.assertEqual([s["id"] for s in data], [hosting.pk])

    def test_services_invoiced_hours(self):
        """Services split their logged hours into invoiced and not invoiced ones"""
        project = factories.ProjectFactory.create()
        service = factories.ServiceFactory.create(
            project=project, external_reference="https://example.com/issues/1"
        )
        factories.ServiceFactory.create(
            project=project, external_reference="https://example.com/issues/12"
        )
        factories.LoggedHoursFactory.create(service=service, hours=3)
        invoice = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            type=Invoice.SERVICES,
        )
        invoice.create_services_from_logbook([service])
        factories.LoggedHoursFactory.create(service=service, hours=2)
        self.client.force_login(project.owned_by)

        data = self.client.get(
            "/api/services/", {"external_reference": "https://example.com/issues/1"}
        ).json()["items"]
        self.assertEqual(
            [
                (
                    s["id"],
                    s["logged_hours"],
                    s["invoiced_hours"],
                    s["not_invoiced_hours"],
                )
                for s in data
            ],
            [(service.pk, "5.0", "3.0", "2.0")],
        )

    def test_service_external_reference(self):
        """The external reference of services can be changed in any state of
        their offer, also of services without offer"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        service = factories.ServiceFactory.create(project=project, offer=offer)
        Offer.objects.filter(pk=offer.pk).update(status=Offer.ACCEPTED)
        self.client.force_login(project.owned_by)
        url = f"/api/services/{service.pk}/"

        def patch(data, query=""):
            return self.client.patch(
                f"{url}{query}", data, content_type="application/json"
            )

        response = patch(
            {"external_reference": " https://example.com/issues/1 "}, "?dry_run=1"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json()["external_reference"], "https://example.com/issues/1"
        )
        service.refresh_from_db()
        self.assertEqual(service.external_reference, "")

        response = patch({"external_reference": "https://example.com/issues/1"})
        self.assertEqual(response.json()["offer"], offer.code)
        service.refresh_from_db()
        self.assertEqual(service.external_reference, "https://example.com/issues/1")

        response = patch({"external_reference": None})
        self.assertEqual(response.json()["external_reference"], "")

        response = patch({"external_reference": "x" * 501})
        self.assertEqual(response.status_code, 422)
        for value in ["issue 1", "https://example.com/1 https://example.com/2"]:
            with self.subTest(value=value):
                response = patch({"external_reference": value})
                self.assertEqual(response.status_code, 422, response.content)
        self.assertEqual(
            self.client.patch(
                "/api/services/0/", {}, content_type="application/json"
            ).status_code,
            404,
        )

    def test_service_move_to_offer(self):
        """Services are moved between offers with the rules of the web
        interface: only offers of the same project which are in preparation
        or service groups, and not out of offers which have been sent"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        group = factories.OfferFactory.create(
            project=project, status=Offer.SERVICE_GROUP
        )
        accepted = factories.OfferFactory.create(project=project)
        Offer.objects.filter(pk=accepted.pk).update(status=Offer.ACCEPTED)
        other = factories.OfferFactory.create()
        service = factories.ServiceFactory.create(project=project, title="Design")
        self.client.force_login(project.owned_by)
        url = f"/api/services/{service.pk}/"

        def patch(data, query=""):
            return self.client.patch(
                f"{url}{query}", data, content_type="application/json"
            )

        def locs(response):
            self.assertEqual(response.status_code, 422, response.content)
            return [e["loc"] for e in response.json()["detail"]]

        response = patch({"offer": offer.pk}, "?dry_run=1")
        self.assertEqual(response.json()["offer"], offer.code)
        service.refresh_from_db()
        self.assertIsNone(service.offer)

        response = patch({"offer": offer.pk})
        self.assertEqual(response.json()["offer"], offer.code)
        response = patch({"offer": group.pk})
        self.assertEqual(response.json()["offer"], group.code)
        response = patch({"offer": None})
        self.assertIsNone(response.json()["offer"])

        self.assertEqual(
            locs(patch({"offer": accepted.pk})), [["body", "data", "offer"]]
        )
        self.assertEqual(locs(patch({"offer": other.pk})), [["body", "data", "offer"]])

        service.offer = accepted
        service.save()
        self.assertEqual(locs(patch({"offer": offer.pk})), [["body", "data", "offer"]])
        # The external reference can still be changed
        response = patch({"external_reference": "https://example.com/issues/2"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["offer"], accepted.code)

        # The title and the description of services of sent offers are locked too
        self.assertEqual(
            locs(patch({"description": "Text"})), [["body", "data", "description"]]
        )
        self.assertEqual(locs(patch({"title": "Text"})), [["body", "data", "title"]])

        # Warnings about the fields which aren't changed don't get in the way
        unspecific = factories.ServiceFactory.create(
            project=project, title="Programmierung allgemein"
        )
        response = self.client.patch(
            f"/api/services/{unspecific.pk}/",
            {"offer": offer.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_service_warnings(self):
        """Warnings of the service form are errors unless they are ignored,
        only for the fields which are changed"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        def send(method, url, data, query=""):
            response = getattr(self.client, method)(
                f"{url}{query}", data, content_type="application/json"
            )
            return response.status_code, [
                e.get("code") for e in response.json().get("detail", [])
            ]

        data = {"project": project.pk, "title": "Allgemein"}
        self.assertEqual(
            send("post", "/api/services/", data), (422, ["unspecific-service"])
        )
        self.assertEqual(
            send(
                "post",
                "/api/services/",
                data | {"description": "https://example.com/issues/1"},
                "?ignore_warnings=unspecific-service",
            ),
            (422, ["description-only-url"]),
        )
        self.assertEqual(
            send(
                "post",
                "/api/services/",
                data,
                "?ignore_warnings=unspecific-service",
            ),
            (200, []),
        )
        service = project.services.get()
        url = f"/api/services/{service.pk}/"
        self.assertEqual(send("patch", url, {"hours": 5}), (200, []))
        self.assertEqual(
            send("patch", url, {"title": "Allg."}), (422, ["unspecific-service"])
        )

    def test_invoiced_service(self):
        """Services which have been invoiced (e.g. from the offer, without
        logged hours) aren't deleted, but may move to another offer of the
        project: the invoice lines still point to them"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        service = factories.ServiceFactory.create(project=project, title="Design")
        invoice = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            type=Invoice.SERVICES,
        )
        invoice.create_services_from_offer([service])
        self.client.force_login(project.owned_by)
        url = f"/api/services/{service.pk}/"

        response = self.client.patch(
            url, {"offer": offer.pk}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        service.refresh_from_db()
        self.assertEqual(service.offer, offer)

        response = self.client.patch(
            url, {"title": "Design and concept"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)

        response = self.client.delete(url)
        self.assertEqual(response.status_code, 422, response.content)
        self.assertEqual(
            response.json()["detail"][0]["msg"],
            "This service has been invoiced already, it cannot be deleted.",
        )
        self.assertTrue(Service.objects.filter(pk=service.pk).exists())

    def test_service_merge(self):
        """Merging moves the invoice lines too and deletes the merged
        service, different rates are a warning"""
        project = factories.ProjectFactory.create()
        service = factories.ServiceFactory.create(project=project, effort_rate=150)
        keep = factories.ServiceFactory.create(project=project, effort_rate=180)
        factories.LoggedHoursFactory.create(service=service, hours=2)
        invoice = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            type=Invoice.SERVICES,
        )
        invoice.create_services_from_logbook([service])
        self.client.force_login(project.owned_by)
        url = f"/api/services/{service.pk}/merge/"

        response = self.client.post(
            url, {"into": keep.pk}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422, response.content)
        self.assertEqual(response.json()["detail"][0]["code"], "different-rate")

        response = self.client.post(
            url + "?ignore_warnings=different-rate&dry_run=true",
            {"into": keep.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(Service.objects.filter(pk=service.pk).exists())

        response = self.client.post(
            url + "?ignore_warnings=different-rate",
            {"into": keep.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["id"], keep.pk)
        self.assertEqual(response.json()["invoiced_hours"], "2.0")
        self.assertFalse(Service.objects.filter(pk=service.pk).exists())
        self.assertTrue(keep.is_invoiced)

    def test_service_move(self):
        """Services are moved to other open projects like in the web
        interface: a flat rate of the new project is a warning and applied,
        invoiced services and services bound to an offer stay"""
        service = factories.ServiceFactory.create(
            effort_type="Programming", effort_rate=150
        )
        project = service.project
        other = factories.ProjectFactory.create()
        closed = factories.ProjectFactory.create(closed_on=dt.date.today())
        flat_rate = factories.ProjectFactory.create(flat_rate=100)
        self.client.force_login(project.owned_by)
        url = f"/api/services/{service.pk}/move/"

        def post(data, query=""):
            return self.client.post(
                f"{url}{query}", data, content_type="application/json"
            )

        def errors(response):
            self.assertEqual(response.status_code, 422, response.content)
            return [(e["loc"], e.get("code")) for e in response.json()["detail"]]

        response = post({"project": other.code}, "?dry_run=1")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["project"]["id"], other.pk)
        service.refresh_from_db()
        self.assertEqual(service.project, project)

        response = post({"project": other.pk})
        self.assertEqual(response.status_code, 200, response.content)
        service.refresh_from_db()
        self.assertEqual(service.project, other)

        self.assertEqual(
            errors(post({"project": closed.pk})), [(["body", "data", "project"], None)]
        )
        self.assertEqual(
            errors(post({"project": 0})), [(["body", "data", "project"], None)]
        )
        self.assertEqual(
            errors(post({"project": flat_rate.pk})),
            [(["body", "data"], "new-project-has-flat-rate")],
        )
        response = post(
            {"project": flat_rate.pk}, "?ignore_warnings=new-project-has-flat-rate"
        )
        self.assertEqual(response.status_code, 200, response.content)
        service.refresh_from_db()
        self.assertEqual(service.project, flat_rate)
        self.assertEqual(service.effort_rate, 100)

        # Services bound to an offer stay with the offer's project
        offer = factories.OfferFactory.create(project=project)
        bound = factories.ServiceFactory.create(project=project, offer=offer)
        response = self.client.post(
            f"/api/services/{bound.pk}/move/",
            {"project": other.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422, response.content)
        self.assertEqual(
            response.json()["detail"],
            [
                {
                    "loc": ["body", "data"],
                    "msg": "The offer must belong to the same project as the service.",
                }
            ],
        )

        # Invoiced services stay with the project of the invoice
        invoiced = factories.ServiceFactory.create(project=project)
        invoice = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            type=Invoice.SERVICES,
        )
        invoice.create_services_from_offer([invoiced])
        response = self.client.post(
            f"/api/services/{invoiced.pk}/move/",
            {"project": other.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422, response.content)
        self.assertEqual(
            response.json()["detail"],
            [
                {
                    "loc": ["body", "data", "project"],
                    "msg": "This service has been invoiced already,"
                    " it cannot be moved to another project.",
                }
            ],
        )
        invoiced.refresh_from_db()
        self.assertEqual(invoiced.project, project)

        self.assertEqual(
            self.client.post(
                "/api/services/0/move/",
                {"project": other.pk},
                content_type="application/json",
            ).status_code,
            404,
        )

    def test_service_description(self):
        """Descriptions of services which aren't bound to sent offers can be
        changed, e.g. to move URLs into the external reference"""
        service = factories.ServiceFactory.create(
            description="https://example.com/issues/1"
        )
        self.client.force_login(service.project.owned_by)
        response = self.client.patch(
            f"/api/services/{service.pk}/",
            {"description": "", "external_reference": "https://example.com/issues/1"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        service.refresh_from_db()
        self.assertEqual(service.description, "")
        self.assertEqual(service.external_reference, "https://example.com/issues/1")

    def test_service_reassign_logbook(self):
        """Logged hours and costs are reassigned like in the web interface,
        invoiced entries only if they are included"""
        project = factories.ProjectFactory.create()
        service = factories.ServiceFactory.create(project=project)
        target = factories.ServiceFactory.create(project=project)
        factories.LoggedHoursFactory.create(service=service, hours=3)
        invoice = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            type=Invoice.SERVICES,
        )
        invoice.create_services_from_logbook([service])
        factories.LoggedHoursFactory.create(service=service, hours=2)
        factories.LoggedCostFactory.create(service=service, cost=50)
        self.client.force_login(project.owned_by)
        url = f"/api/services/{service.pk}/reassign-logbook/"

        def post(data, query=""):
            return self.client.post(
                f"{url}{query}", data, content_type="application/json"
            )

        response = post({"to": target.pk}, "?dry_run=1")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response.json()["hours"], response.json()["costs"]), (1, 1))
        self.assertEqual(target.loggedhours.count(), 0)

        response = post({"to": target.pk})
        data = response.json()
        self.assertEqual((data["hours"], data["costs"]), (1, 1))
        self.assertEqual(data["to"]["id"], target.pk)
        self.assertEqual(data["from"]["logged_hours"], "3.0")
        self.assertEqual(target.loggedhours.count(), 1)

        response = post({"to": target.pk, "include_invoiced": True})
        self.assertEqual((response.json()["hours"], response.json()["costs"]), (1, 0))
        self.assertEqual(service.loggedhours.count(), 0)

        # Only services of the same project which allow logging
        closed = factories.ServiceFactory.create(project=project, allow_logging=False)
        for other in [factories.ServiceFactory.create(), closed]:
            response = post({"to": other.pk})
            self.assertEqual(response.status_code, 422)
            self.assertEqual(
                [e["loc"] for e in response.json()["detail"]], [["body", "data", "to"]]
            )

    def test_service_title(self):
        """Titles of services which aren't bound to sent offers can be changed,
        e.g. to the title of their issue; they are required"""
        service = factories.ServiceFactory.create(title="#12 Old title")
        self.client.force_login(service.project.owned_by)

        def patch(data):
            return self.client.patch(
                f"/api/services/{service.pk}/", data, content_type="application/json"
            )

        response = patch({"title": " #12 New title of the issue "})
        self.assertEqual(response.status_code, 200, response.content)
        service.refresh_from_db()
        self.assertEqual(service.title, "#12 New title of the issue")

        response = patch({"title": ""})
        self.assertEqual(response.status_code, 422, response.content)
        service.refresh_from_db()
        self.assertEqual(service.title, "#12 New title of the issue")

    def test_service_fields(self):
        """All fields of the web form can be changed, service types fill in
        the effort type and the rate; sent offers lock everything but the
        external reference"""
        factories.service_types()
        project = factories.ProjectFactory.create()
        service = factories.ServiceFactory.create(project=project, title="Design")
        self.client.force_login(project.owned_by)

        def patch(data, query=""):
            return self.client.patch(
                f"/api/services/{service.pk}/{query}",
                data,
                content_type="application/json",
            )

        response = patch({"service_type": "production", "hours": 5, "cost": 100})
        self.assertEqual(response.status_code, 200, response.content)
        service.refresh_from_db()
        self.assertEqual(service.effort_type, "production")
        self.assertEqual(service.effort_hours, 5)
        self.assertEqual(service.service_cost, 5 * service.effort_rate + 100)

        response = patch({"hours": None, "is_optional": True}, "?dry_run=true")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["service_hours"], "0.0")
        service.refresh_from_db()
        self.assertEqual((service.effort_hours, service.is_optional), (5, False))

        response = patch({"service_type": "unknown"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["loc"], ["body", "data", "service_type"]
        )

        offer = factories.OfferFactory.create(project=project)
        Offer.objects.filter(pk=offer.pk).update(status=Offer.ACCEPTED)
        service.offer = offer
        service.save()
        response = patch({"hours": 1, "external_reference": "https://example.com/1"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"] for error in response.json()["detail"]],
            [["body", "data", "hours"]],
        )
        response = patch({"external_reference": "https://example.com/1"})
        self.assertEqual(response.status_code, 200, response.content)

    def test_service_create_and_reorder_with_headings(self):
        """Headings stay in their place when the services of an offer are
        reordered, services created after another one come right after it"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        first = factories.ServiceFactory.create(project=project, offer=offer)
        second = factories.ServiceFactory.create(project=project, offer=offer)
        heading = OfferHeading.objects.create(
            offer=offer, title="Later", position=first.position + 1
        )
        self.client.force_login(project.owned_by)
        self.assertEqual(offer.items(), [first, heading, second])

        response = self.client.post(
            "/api/services/reorder/",
            {"services": [second.pk, first.pk]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(offer.items(), [second, heading, first])

        response = self.client.post(
            "/api/services/",
            {"offer": offer.pk, "title": "Added", "after": second.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        added = Service.objects.get(title="Added")
        self.assertEqual(offer.items(), [second, added, heading, first])

    def test_service_create_delete_reorder(self):
        """Services are created at the end of their group or after another
        service, deleted and reordered like in the web interface"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        first = factories.ServiceFactory.create(project=project, offer=offer)
        second = factories.ServiceFactory.create(project=project, offer=offer)
        loose = factories.ServiceFactory.create(project=project)
        self.client.force_login(project.owned_by)

        def post(url, data, query=""):
            return self.client.post(
                f"{url}{query}", data, content_type="application/json"
            )

        def order():
            return list(offer.services.values_list("pk", flat=True))

        response = post(
            "/api/services/",
            {"offer": offer.pk, "title": "Concept", "after": first.pk},
            "?dry_run=true",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.json()["id"])
        self.assertEqual(order(), [first.pk, second.pk])

        response = post(
            "/api/services/", {"offer": offer.pk, "title": "Concept", "after": first.pk}
        )
        self.assertEqual(response.status_code, 200, response.content)
        created = response.json()["id"]
        self.assertEqual(response.json()["project"]["id"], project.pk)
        self.assertEqual(order(), [first.pk, created, second.pk])

        # Not after services of other groups, and a project or an offer is needed
        response = post(
            "/api/services/", {"offer": offer.pk, "title": "X", "after": loose.pk}
        )
        self.assertEqual(response.status_code, 422)
        response = post("/api/services/", {"title": "X"})
        self.assertEqual(response.status_code, 422)
        response = post("/api/services/", {"project": project.pk, "title": "Loose"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.json()["offer"])

        # Reorder all services of one group
        response = post("/api/services/reorder/", {"services": [second.pk, first.pk]})
        self.assertEqual(response.status_code, 422)
        response = post(
            "/api/services/reorder/", {"services": [second.pk, first.pk, loose.pk]}
        )
        self.assertEqual(response.status_code, 422)
        response = post(
            "/api/services/reorder/", {"services": [second.pk, created, first.pk]}
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            [s["id"] for s in response.json()], [second.pk, created, first.pk]
        )
        self.assertEqual(order(), [second.pk, created, first.pk])

        # Services of offers which have been sent stay in their order
        Offer.objects.filter(pk=offer.pk).update(status=Offer.OFFERED)
        response = post(
            "/api/services/reorder/", {"services": [first.pk, created, second.pk]}
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(order(), [second.pk, created, first.pk])
        response = self.client.post(
            Service.urls["set_order"], {"ids": [first.pk, created, second.pk]}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(order(), [second.pk, created, first.pk])
        Offer.objects.filter(pk=offer.pk).update(status=Offer.IN_PREPARATION)

        # Delete, not with logged hours and not out of sent offers
        response = self.client.delete(f"/api/services/{created}/?dry_run=true")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(offer.services.count(), 3)
        response = self.client.delete(f"/api/services/{created}/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(order(), [second.pk, first.pk])
        factories.LoggedHoursFactory.create(service=first)
        response = self.client.delete(f"/api/services/{first.pk}/")
        self.assertEqual(response.status_code, 422)
        Offer.objects.filter(pk=offer.pk).update(status=Offer.OFFERED)
        response = self.client.delete(f"/api/services/{second.pk}/")
        self.assertEqual(response.status_code, 422)

    def test_deals(self):
        """Projects and offers list their deals, projects also those linked
        through an offer; null without the deals feature"""
        offer = factories.OfferFactory.create()
        project = offer.project
        other = factories.OfferFactory.create(project=project)
        direct = factories.DealFactory.create(title="Maintenance")
        direct.related_projects.add(project)
        through = factories.DealFactory.create(title="Relaunch")
        through.related_offers.add(offer)
        factories.DealFactory.create()
        self.client.force_login(project.owned_by)

        def titles(url):
            deals = self.client.get(url).json()["deals"]
            return None if deals is None else [deal["title"] for deal in deals]

        self.assertEqual(
            titles(f"/api/projects/{project.pk}/"), ["Relaunch", "Maintenance"]
        )
        self.assertEqual(titles(f"/api/offers/{offer.pk}/"), ["Relaunch"])
        self.assertEqual(titles(f"/api/offers/{other.pk}/"), [])
        deal = self.client.get(f"/api/offers/{offer.pk}/").json()["deals"][0]
        self.assertEqual(deal["status"], "open")
        self.assertEqual(deal["code"], through.code)

        with override_settings(
            FEATURES={FEATURES.CONTROLLING: F.ALWAYS, FEATURES.DEALS: F.NEVER}
        ):
            self.assertIsNone(titles(f"/api/projects/{project.pk}/"))
            self.assertIsNone(titles(f"/api/offers/{offer.pk}/"))

    @override_settings(FEATURES={FEATURES.CONTROLLING: F.NEVER})
    def test_services_rates_require_controlling(self):
        """Rates require the controlling feature, like on the project page"""
        service = factories.ServiceFactory.create(
            effort_type="Design", effort_hours=10, effort_rate=200
        )
        self.client.force_login(service.project.owned_by)
        data = self.client.get("/api/services/").json()["items"]
        self.assertIsNone(data[0]["effort_rate"])

    def test_close_without_planned_work(self):
        """Answering the planned work question which isn't asked is fine"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.patch(
            f"/api/projects/{project.pk}/",
            {"closed_on": dt.date.today().isoformat(), "delete_planned_work": False},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        project.refresh_from_db()
        self.assertEqual(project.closed_on, dt.date.today())

    def test_update(self):
        """Projects are changed field by field and closed like in the web
        interface"""
        project = factories.ProjectFactory.create(title="Relaunch")
        self.client.force_login(project.owned_by)
        url = f"/api/projects/{project.pk}/"

        def patch(data, query=""):
            return self.client.patch(
                f"{url}{query}", data, content_type="application/json"
            )

        response = patch({"title": "Website"}, "?dry_run=true")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["title"], "Website")
        project.refresh_from_db()
        self.assertEqual(project.title, "Relaunch")

        response = patch({"closed_on": dt.date.today().isoformat()})
        self.assertEqual(response.json()["closed_on"], dt.date.today().isoformat())
        project.refresh_from_db()
        self.assertEqual(
            (project.title, project.closed_on), ("Relaunch", dt.date.today())
        )

        response = patch({"closed_on": None})
        project.refresh_from_db()
        self.assertIsNone(project.closed_on)

        # Planned work of offers which are discarded when closing needs a
        # decision
        offer = factories.OfferFactory.create(project=project)
        factories.PlannedWorkFactory.create(
            project=project, offer=offer, weeks=[monday() + dt.timedelta(days=7)]
        )
        response = patch({"closed_on": dt.date.today().isoformat()})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [e["loc"] for e in response.json()["detail"]],
            [["body", "data", "delete_planned_work"]],
        )
        response = patch({
            "closed_on": dt.date.today().isoformat(),
            "delete_planned_work": False,
        })
        self.assertEqual(response.status_code, 200, response.content)
        offer.refresh_from_db()
        self.assertEqual(offer.status, Offer.DISCARDED)
        self.assertEqual(offer.planned_work.count(), 1)
        patch({"closed_on": None})

        # Warnings of the web interface are errors
        factories.InvoiceFactory.create(project=project, customer=project.customer)
        response = patch({
            "customer": factories.OrganizationFactory.create().pk,
            "contact": None,
        })
        self.assertEqual(response.status_code, 422)
        self.assertIn("already has invoices", response.content.decode())

        response = patch({"owned_by": "nobody"})
        self.assertEqual(response.status_code, 422)

    @override_settings(
        FEATURES={
            FEATURES.CAMPAIGNS: F.ALWAYS,
            FEATURES.CONTROLLING: F.ALWAYS,
            FEATURES.LABOR_COSTS: F.ALWAYS,
            FEATURES.PLANNING: F.ALWAYS,
        }
    )
    def test_update_all_fields(self):
        """Every field of the project form can be changed"""
        project = factories.ProjectFactory.create()
        campaign = factories.CampaignFactory.create(customer=project.customer)
        cost_center = factories.CostCenterFactory.create(title="Development")
        self.client.force_login(project.owned_by)
        url = f"/api/projects/{project.pk}/"

        def patch(data, query=""):
            return self.client.patch(
                f"{url}{query}", data, content_type="application/json"
            )

        response = patch({
            "campaign": campaign.pk,
            "cost_center": "development",
            "flat_rate": 160,
            "budget_alert_at": 8000,
            "suppress_planning_update_mails": True,
        })
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["campaign"]["id"], campaign.pk)
        self.assertEqual(data["cost_center"], "Development")
        self.assertEqual(data["flat_rate"], "160.00")
        self.assertEqual(data["budget_alert_at"], "8000.00")
        self.assertTrue(data["suppress_planning_update_mails"])
        project.refresh_from_db()
        self.assertEqual(project.campaign, campaign)
        self.assertEqual(project.cost_center, cost_center)
        self.assertEqual(project.flat_rate, Decimal("160.00"))
        self.assertEqual(project.budget_alert_at, Decimal("8000.00"))
        self.assertTrue(project.suppress_planning_update_mails)

        data = self.client.get(url).json()
        self.assertEqual(data["cost_center"], "Development")
        self.assertEqual(data["budget_alert_at"], "8000.00")

        # IDs of cost centers work too, unknown ones and campaigns are errors
        response = patch({"cost_center": str(cost_center.pk)})
        self.assertEqual(response.status_code, 200, response.content)
        response = patch({"cost_center": "Sales", "campaign": 0})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            sorted(e["loc"][-1] for e in response.json()["detail"]),
            ["campaign", "cost_center"],
        )

        # The flat rate overwrites the rates of services, a warning
        service = factories.ServiceFactory.create(
            project=project, effort_type="Design", effort_rate=200, effort_hours=1
        )
        response = patch({"flat_rate": 180})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["code"], "flat-rate-but-already-services"
        )
        response = patch(
            {"flat_rate": 180}, "?ignore_warnings=flat-rate-but-already-services"
        )
        self.assertEqual(response.status_code, 200, response.content)

        # null empties the fields
        response = patch({
            "campaign": None,
            "cost_center": None,
            "flat_rate": None,
            "budget_alert_at": None,
            "suppress_planning_update_mails": None,
        })
        self.assertEqual(response.status_code, 200, response.content)
        project.refresh_from_db()
        self.assertEqual(
            (
                project.campaign,
                project.cost_center,
                project.flat_rate,
                project.budget_alert_at,
                project.suppress_planning_update_mails,
            ),
            (None, None, None, None, False),
        )
        service.refresh_from_db()
        self.assertEqual(service.effort_rate, Decimal("180.00"))

    @override_settings(FEATURES={FEATURES.CONTROLLING: F.ALWAYS})
    def test_update_fields_without_feature(self):
        """Fields of features the user doesn't have can't be changed, like in
        the web interface where they're missing"""
        project = factories.ProjectFactory.create()
        factories.CostCenterFactory.create(title="Anything")
        self.client.force_login(project.owned_by)
        response = self.client.patch(
            f"/api/projects/{project.pk}/",
            {
                "campaign": factories.CampaignFactory.create().pk,
                "cost_center": "Anything",
                "suppress_planning_update_mails": True,
                "flat_rate": 100,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            sorted(e["loc"][-1] for e in response.json()["detail"]),
            ["campaign", "cost_center", "suppress_planning_update_mails"],
        )

    def test_delete(self):
        """Projects are deleted like in the web interface, unless something
        depends on them"""
        project = factories.ProjectFactory.create(title="Mistake")
        factories.ServiceFactory.create(project=project)
        self.client.force_login(project.owned_by)
        url = f"/api/projects/{project.pk}/"

        response = self.client.delete(f"{url}?dry_run=true")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["title"], "Mistake")
        self.assertTrue(Project.objects.filter(pk=project.pk).exists())

        offer = factories.OfferFactory.create(project=project)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"][0]["loc"], ["path", "project_id"])
        self.assertIn("Cannot delete", response.json()["detail"][0]["msg"])
        offer.delete()

        response = self.client.delete(f"/api/projects/{project.code}/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["id"], project.pk)
        self.assertFalse(Project.objects.filter(pk=project.pk).exists())

    def test_projected_invoices(self):
        """The projected invoices of a project are replaced like in the web
        interface's formset, with its freeze date rules"""
        project = factories.ProjectFactory.create()
        past = factories.ProjectedInvoiceFactory.create(
            project=project, invoiced_on=in_days(-30), gross_margin=1000
        )
        removed = factories.ProjectedInvoiceFactory.create(
            project=project, invoiced_on=in_days(10), gross_margin=500
        )
        FreezeDate.objects.create(up_to=in_days(-5))
        self.client.force_login(project.owned_by)
        url = f"/api/projects/{project.pk}/projected-invoices/"

        def put(items, query=""):
            return self.client.put(
                f"{url}{query}",
                {"projected_invoices": items},
                content_type="application/json",
            )

        items = [
            # Same date as an existing one: changed, not deleted and created
            {"invoiced_on": in_days(-30).isoformat(), "gross_margin": 1200},
            {
                "invoiced_on": in_days(40).isoformat(),
                "gross_margin": 3000,
                "description": "Phase 2",
            },
        ]
        response = put(items, "?dry_run=true")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(
            [(row["id"], row["gross_margin"]) for row in data["projected_invoices"]],
            [(past.pk, "1200.00"), (None, "3000.00")],
        )
        self.assertEqual(data["total"], "4200.00")
        self.assertEqual(data["project"]["id"], project.pk)
        self.assertEqual(
            set(project.projected_invoices.values_list("pk", flat=True)),
            {past.pk, removed.pk},
        )

        response = put(items)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            list(
                project.projected_invoices.values_list(
                    "id", "gross_margin", "description"
                )
            ),
            [
                (past.pk, Decimal("1200.00"), ""),
                (response.json()["projected_invoices"][1]["id"], 3000, "Phase 2"),
            ],
        )

        # Not on or before the freeze date
        response = put([
            {"id": past.pk, "invoiced_on": in_days(-10).isoformat(), "gross_margin": 1},
            {"invoiced_on": in_days(-6).isoformat(), "gross_margin": 1},
        ])
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [e["loc"] for e in response.json()["detail"]],
            [
                ["body", "data", "projected_invoices", 0, "invoiced_on"],
                ["body", "data", "projected_invoices", 1, "invoiced_on"],
            ],
        )

        # IDs of other projects' projections are refused, and IDs twice
        other = factories.ProjectedInvoiceFactory.create(invoiced_on=in_days(20))
        response = put([
            {"id": other.pk, "invoiced_on": in_days(20).isoformat(), "gross_margin": 1},
            {"id": past.pk, "invoiced_on": in_days(-30).isoformat(), "gross_margin": 1},
            {"id": past.pk, "invoiced_on": in_days(-30).isoformat(), "gross_margin": 1},
        ])
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [e["loc"] for e in response.json()["detail"]],
            [
                ["body", "data", "projected_invoices", 0, "id"],
                ["body", "data", "projected_invoices", 2, "id"],
            ],
        )

        # Closed projects get no new projections, but can lose them
        project.closed_on = in_days(0)
        project.save()
        response = put([{"invoiced_on": in_days(50).isoformat(), "gross_margin": 1}])
        self.assertEqual(response.status_code, 422)
        self.assertIn("already closed", response.content.decode())
        response = put([])
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["projected_invoices"], [])
        self.assertEqual(response.json()["total"], "0.00")
        self.assertFalse(project.projected_invoices.exists())

    @override_settings(FEATURES={FEATURES.CONTROLLING: F.ALWAYS})
    def test_projected_invoices_feature(self):
        """Projected invoices require their feature, like in the web interface"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)
        response = self.client.put(
            f"/api/projects/{project.pk}/projected-invoices/",
            {"projected_invoices": []},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
