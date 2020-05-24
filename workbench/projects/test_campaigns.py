from django.test import TestCase

from workbench import factories
from workbench.projects.models import Campaign, Project
from workbench.tools.forms import WarningsForm
from workbench.tools.testing import check_code


class CampaignsTest(TestCase):
    def test_crud(self):
        """Campaign CRUD"""
        user = factories.UserFactory.create()
        self.client.force_login(user)

        organization = factories.OrganizationFactory.create()

        response = self.client.get(Campaign.urls["create"] + "?customer=bla")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            Campaign.urls["create"] + "?customer={}".format(organization.id)
        )
        self.assertContains(response, 'value="The Organization Ltd"')

        response = self.client.post(
            Campaign.urls["create"],
            {
                "customer": organization.pk,
                "title": "Test campaign",
                "owned_by": user.pk,
            },
        )
        campaign = Campaign.objects.get()
        self.assertEqual(campaign.customer, organization)
        self.assertRedirects(response, campaign.urls["detail"])

        response = self.client.get(campaign.urls["delete"])
        self.assertNotContains(response, WarningsForm.ignore_warnings_id)

        project = factories.ProjectFactory.create(campaign=campaign)

        response = self.client.get(campaign.urls["delete"])
        self.assertContains(response, WarningsForm.ignore_warnings_id)

        response = self.client.post(
            campaign.urls["delete"],
            {WarningsForm.ignore_warnings_id: "release-projects"},
        )
        self.assertRedirects(response, Campaign.urls["list"])

        project.refresh_from_db()
        self.assertIs(project.campaign, None)

    def test_create_project_with_campaign(self):
        """Preselecting the campaign when creating a project works"""
        campaign = factories.CampaignFactory.create()
        self.client.force_login(campaign.owned_by)

        response = self.client.get(
            Project.urls["create"] + "?campaign={}".format(campaign.pk)
        )
        self.assertContains(response, 'value="{}"'.format(str(campaign)))

    def test_statistics(self):
        """Campaign statistics do not crash"""
        campaign = factories.CampaignFactory.create()
        factories.ProjectFactory.create(campaign=campaign)
        factories.ProjectFactory.create(campaign=campaign)

        self.assertEqual(len(campaign.statistics["statistics"]), 2)
        self.assertIs(campaign.statistics["overall"]["gross_margin_per_hour"], None)

    def test_lists(self):
        """Filter form smoke test"""
        campaign = factories.CampaignFactory.create()
        self.client.force_login(campaign.owned_by)

        code = check_code(self, Campaign.urls["list"])
        code("")
        code("q=test")
        code("s=")
        code("s=open")
        code("s=closed")
        code("org={}".format(campaign.customer_id))
        code("owned_by={}".format(campaign.owned_by_id))
        code("owned_by=-1")  # mine
        code("owned_by=0")  # only inactive

        code("invalid=3", 302)

    def test_autocomplete(self):
        """Test the autocomplete endpoints of contacts and projects"""
        campaign = factories.CampaignFactory.create()
        self.client.force_login(campaign.owned_by)

        self.assertEqual(
            self.client.get(Campaign.urls["autocomplete"] + "?q=campa").json(),
            {"results": [{"label": str(campaign), "value": campaign.id}]},
        )

    def test_copy(self):
        """Copying campaigns works"""
        campaign = factories.CampaignFactory.create()
        self.client.force_login(campaign.owned_by)

        response = self.client.get(
            campaign.urls["create"] + "?copy=" + str(campaign.pk)
        )
        self.assertContains(response, 'value="{}"'.format(campaign.title))

        response = self.client.get(campaign.urls["create"] + "?copy=blub")
        self.assertEqual(response.status_code, 200)  # No crash
