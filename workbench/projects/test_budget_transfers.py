import datetime as dt
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test.utils import override_settings
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.invoices.models import Invoice
from workbench.projects.models import BudgetTransfer
from workbench.reporting.project_budget_statistics import project_budget_statistics
from workbench.reporting.squeeze import project_gross_margin, squeeze_data
from workbench.tools.forms import WarningsForm
from workbench.tools.validation import in_days


class BudgetTransferTest(TestCase):
    """
    The scenario: a campaign website project is invoiced and closed, and part of
    its budget was reserved for a later re-conception which happens on a new
    project. Closed projects cannot be reopened, so the hours land on a project
    without revenue.
    """

    def setUp(self):
        deactivate_all()

    def campaign_project(self, *, user, invoiced, hours):
        """A closed project with an invoice and some logged hours."""
        project = factories.ProjectFactory.create(owned_by=user)
        service = factories.ServiceFactory.create(
            project=project, effort_rate=100, effort_type="Any"
        )
        factories.LoggedHoursFactory.create(
            service=service, rendered_by=user, created_by=user, hours=hours
        )
        factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            owned_by=user,
            type=Invoice.FIXED,
            subtotal=invoiced,
            status=Invoice.PAID,
            invoiced_on=in_days(-30),
            due_on=in_days(-15),
            closed_on=in_days(-10),
        )
        project.closed_on = dt.date.today()
        project.save()
        return project

    def reconception_project(self, *, user, hours):
        """An open project with hours but no revenue of its own."""
        project = factories.ProjectFactory.create(owned_by=user)
        service = factories.ServiceFactory.create(
            project=project, effort_rate=100, effort_type="Any"
        )
        factories.LoggedHoursFactory.create(
            service=service, rendered_by=user, created_by=user, hours=hours
        )
        return project

    def test_rates_without_a_transfer(self):
        """Without a transfer the source looks great and the target worthless"""
        user = factories.UserFactory.create()
        source = self.campaign_project(user=user, invoiced=Decimal(12000), hours=40)
        target = self.reconception_project(user=user, hours=40)

        self.assertEqual(project_gross_margin(source)["rate"], Decimal(300))
        self.assertEqual(project_gross_margin(target)["rate"], Decimal(0))

    def test_transfer_moves_the_rate_along(self):
        """Moving budget puts the money next to the hours it paid for"""
        user = factories.UserFactory.create()
        source = self.campaign_project(user=user, invoiced=Decimal(12000), hours=40)
        target = self.reconception_project(user=user, hours=40)

        BudgetTransfer.objects.create(
            from_project=source,
            to_project=target,
            title="Re-Konzeption",
            amount=Decimal(8000),
            created_by=user,
        )

        self.assertEqual(project_gross_margin(source)["rate"], Decimal(100))
        self.assertEqual(project_gross_margin(target)["rate"], Decimal(200))

    def test_reserving_without_a_target_already_helps(self):
        """Budget leaves the source even before a target project exists"""
        user = factories.UserFactory.create()
        source = self.campaign_project(user=user, invoiced=Decimal(12000), hours=40)

        transfer = BudgetTransfer.objects.create(
            from_project=source,
            title="Reserved for the re-conception",
            amount=Decimal(8000),
            created_by=user,
        )
        self.assertTrue(transfer.is_reserved)
        self.assertIn(transfer, BudgetTransfer.objects.reserved())

        # 12'000 - 8'000 reserved over its own 40 hours.
        self.assertEqual(project_gross_margin(source)["rate"], Decimal(100))

    def test_squeeze_report_agrees(self):
        """The squeeze report attributes the moved margin to the later project"""
        user = factories.UserFactory.create()
        source = self.campaign_project(user=user, invoiced=Decimal(12000), hours=40)
        target = self.reconception_project(user=user, hours=40)
        BudgetTransfer.objects.create(
            from_project=source,
            to_project=target,
            title="Re-Konzeption",
            amount=Decimal(8000),
            created_by=user,
        )

        data = squeeze_data([in_days(-7), in_days(7)])
        by_project = {row["project"]: row for row in data["projects"]}
        self.assertEqual(by_project[source]["gross_margin"], Decimal(4000))
        self.assertEqual(by_project[target]["gross_margin"], Decimal(8000))
        self.assertEqual(by_project[source]["rate"], Decimal(100))
        self.assertEqual(by_project[target]["rate"], Decimal(200))

    def test_project_budget_statistics_follows(self):
        """The moved budget changes the cost cap on both projects"""
        user = factories.UserFactory.create()
        source = self.campaign_project(user=user, invoiced=Decimal(12000), hours=40)
        target = self.reconception_project(user=user, hours=40)
        offer = factories.OfferFactory.create(
            project=source, status=factories.Offer.ACCEPTED
        )
        factories.ServiceFactory.create(
            project=source, offer=offer, cost=Decimal(12000)
        )
        offer.save()

        before = {
            s["project"]: s["sold"]
            for s in project_budget_statistics([source, target])["statistics"]
        }
        self.assertEqual(before[source], Decimal(12000))
        self.assertEqual(before[target], Decimal(0))

        BudgetTransfer.objects.create(
            from_project=source,
            to_project=target,
            title="Re-Konzeption",
            amount=Decimal(8000),
            created_by=user,
        )

        after = {
            s["project"]: s["sold"]
            for s in project_budget_statistics([source, target])["statistics"]
        }
        self.assertEqual(after[source], Decimal(4000))
        self.assertEqual(after[target], Decimal(8000))

    def test_cannot_move_budget_to_the_same_project(self):
        """Moving budget onto its own project is rejected"""
        user = factories.UserFactory.create()
        project = factories.ProjectFactory.create(owned_by=user)
        transfer = BudgetTransfer(
            from_project=project,
            to_project=project,
            title="Nonsense",
            amount=Decimal(100),
            created_by=user,
        )
        with self.assertRaises(ValidationError) as cm:
            transfer.clean_fields()
        self.assertIn("to_project", cm.exception.error_dict)

    def test_crud_from_the_project_page(self):
        """Transfers are created, edited and deleted from the source project"""
        user = factories.UserFactory.create()
        source = self.campaign_project(user=user, invoiced=Decimal(12000), hours=40)
        target = self.reconception_project(user=user, hours=40)
        self.client.force_login(user)

        # The project page opens these with data-ajaxmodal, so the form views
        # have to answer with modal markup and not with a whole page.
        response = self.client.get(source.urls["createbudgettransfer"])
        self.assertContains(response, "Available: 12’000.00.")
        self.assertContains(response, '<div class="modal">')
        self.assertNotContains(response, "<!DOCTYPE html>")

        # Reserve first, without naming a target project.
        response = self.client.post(
            source.urls["createbudgettransfer"],
            {
                "modal-title": "Re-Konzeption",
                "modal-amount": "8000",
                "modal-notes": "",
            },
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 201)
        transfer = BudgetTransfer.objects.get()
        self.assertTrue(transfer.is_reserved)

        response = self.client.get(source.get_absolute_url())
        self.assertContains(response, "reserved, no target project yet")
        self.assertContains(response, "8’000.00")

        # Later on, point it at the project which does the work.
        response = self.client.post(
            transfer.urls["update"],
            {
                "modal-to_project": target.pk,
                "modal-title": "Re-Konzeption",
                "modal-amount": "8000",
                "modal-notes": "",
            },
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 202)
        transfer.refresh_from_db()
        self.assertEqual(transfer.to_project, target)

        response = self.client.get(target.get_absolute_url())
        self.assertContains(response, "Re-Konzeption")

        for url in (transfer.urls["update"], transfer.urls["delete"]):
            response = self.client.get(url)
            self.assertContains(response, '<div class="modal">')
            self.assertNotContains(response, "<!DOCTYPE html>")

        # Deleting happens from inside the edit modal, and the row itself is
        # what opens that modal.
        response = self.client.get(transfer.urls["update"])
        self.assertContains(response, transfer.urls["delete"])
        response = self.client.get(source.urls["createbudgettransfer"])
        self.assertNotContains(response, "budget-transfer/")

        response = self.client.get(source.get_absolute_url())
        self.assertContains(response, transfer.urls["update"])
        self.assertContains(response, "stretched-link")

        response = self.client.post(
            transfer.urls["delete"],
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(BudgetTransfer.objects.count(), 0)

    def test_warns_when_moving_more_than_the_project_has(self):
        """Emptying a project's budget past zero has to be confirmed"""
        user = factories.UserFactory.create()
        source = self.campaign_project(user=user, invoiced=Decimal(12000), hours=40)
        self.client.force_login(user)

        response = self.client.post(
            source.urls["createbudgettransfer"],
            {
                "modal-title": "Too much",
                "modal-amount": "20000",
                "modal-notes": "",
            },
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertContains(response, "budget-transfer-too-large")
        self.assertEqual(BudgetTransfer.objects.count(), 0)

        response = self.client.post(
            source.urls["createbudgettransfer"],
            {
                "modal-title": "Too much",
                "modal-amount": "20000",
                "modal-notes": "",
                WarningsForm.ignore_warnings_id: "budget-transfer-too-large",
            },
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 201)

    @override_settings(FEATURES={FEATURES.CONTROLLING: F.NEVER})
    def test_requires_controlling(self):
        """The form shows the gross margin of the project, like the
        profitability modal it requires the controlling feature"""
        project = factories.ProjectFactory.create()
        transfer = BudgetTransfer.objects.create(
            from_project=project,
            title="Reserved",
            amount=100,
            created_by=project.owned_by,
        )
        self.client.force_login(project.owned_by)
        for url in [
            project.urls["createbudgettransfer"],
            transfer.urls["update"],
            transfer.urls["delete"],
        ]:
            with self.subTest(url=url):
                self.assertRedirects(
                    self.client.get(url), "/", fetch_redirect_response=False
                )
