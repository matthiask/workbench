from django.contrib.messages.storage.cookie import CookieStorage
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.utils.translation import deactivate_all
from ninja.errors import ValidationError as NinjaValidationError

from workbench import factories
from workbench.deals.models import Deal
from workbench.offers.forms import OfferDeleteForm
from workbench.offers.models import Offer
from workbench.planning.models import PlannedWork
from workbench.projects.forms import CampaignDeleteForm, ProjectForm
from workbench.projects.models import Campaign, Project, Service
from workbench.tools.api import (
    active_user,
    api_key,
    delete_with_form,
    object_pk,
    patch_with_form,
)
from workbench.tools.validation import monday


def _request(user):
    request = RequestFactory().get("/")
    request.user = user
    request._messages = CookieStorage(request)
    return request


def _errors(cm):
    return [
        {key: error[key] for key in ("loc", "msg", "code") if key in error}
        for error in cm.exception.errors
    ]


class DeleteWithFormTest(TestCase):
    def setUp(self):
        deactivate_all()

    def test_refused_by_allow_delete(self):
        """What the web interface refuses to delete stays refused, its
        messages become errors"""
        offer = factories.OfferFactory.create(status=Offer.ACCEPTED)
        request = _request(offer.owned_by)
        with self.assertRaises(NinjaValidationError) as cm:
            delete_with_form(
                offer,
                request,
                loc=["path", "offer_id"],
                delete_form_class=OfferDeleteForm,
                dry_run=False,
            )
        self.assertEqual(
            _errors(cm),
            [
                {
                    "loc": ["path", "offer_id"],
                    "msg": "Offers which have been sent or accepted cannot be deleted.",
                }
            ],
        )
        self.assertTrue(Offer.objects.filter(pk=offer.pk).exists())

    def test_delete_form_questions(self):
        """The questions of the delete form are its fields, required ones are
        errors located like the caller says"""
        offer = factories.OfferFactory.create()
        offer_pk = offer.pk
        work = factories.PlannedWorkFactory.create(
            project=offer.project, offer=offer, weeks=[monday()]
        )
        request = _request(offer.owned_by)

        def delete(data=None, *, dry_run=False):
            delete_with_form(
                offer,
                request,
                loc=["path", "offer_id"],
                delete_form_class=OfferDeleteForm,
                data=data,
                fields={"delete_planned_work": ["query", "delete_planned_work"]},
                dry_run=dry_run,
            )

        with self.assertRaises(NinjaValidationError) as cm:
            delete()
        self.assertEqual(
            [error["loc"] for error in _errors(cm)],
            [["body", "data", "query", "delete_planned_work"]],
        )

        delete({"delete_planned_work": True}, dry_run=True)
        # Deleting sets the PK to None, also when rolled back
        self.assertTrue(Offer.objects.filter(pk=offer_pk).exists())
        offer = Offer.objects.get(pk=offer_pk)
        self.assertTrue(PlannedWork.objects.filter(pk=work.pk).exists())

        delete({"delete_planned_work": True})
        self.assertFalse(Offer.objects.filter(pk=offer_pk).exists())
        self.assertFalse(PlannedWork.objects.filter(pk=work.pk).exists())

    def test_delete_form_warnings(self):
        """Warnings of the delete form are errors with their code unless
        ignored"""
        campaign = factories.CampaignFactory.create()
        campaign_pk = campaign.pk
        project = factories.ProjectFactory.create(campaign=campaign)
        request = _request(campaign.owned_by)

        with self.assertRaises(NinjaValidationError) as cm:
            delete_with_form(
                campaign,
                request,
                loc=["path", "campaign_id"],
                delete_form_class=CampaignDeleteForm,
                dry_run=False,
            )
        self.assertEqual(
            [error.get("code") for error in _errors(cm)], ["release-projects"]
        )

        delete_with_form(
            campaign,
            request,
            loc=["path", "campaign_id"],
            delete_form_class=CampaignDeleteForm,
            ignore_warnings=["release-projects"],
            dry_run=False,
        )
        self.assertFalse(Campaign.objects.filter(pk=campaign_pk).exists())
        project.refresh_from_db()
        self.assertIsNone(project.campaign)

    def test_without_delete_form(self):
        """Without a delete form the instance is deleted if allow_delete()
        allows it, related objects which protect it refuse"""
        service = factories.ServiceFactory.create()
        pk = service.pk
        request = _request(service.project.owned_by)
        delete_with_form(service, request, loc=["path", "service_id"], dry_run=True)
        self.assertTrue(Service.objects.filter(pk=pk).exists())
        service = Service.objects.get(pk=pk)
        delete_with_form(service, request, loc=["path", "service_id"], dry_run=False)
        self.assertFalse(Service.objects.filter(pk=pk).exists())

        project = factories.ProjectFactory.create()
        factories.InvoiceFactory.create(
            project=project, customer=project.customer, contact=project.contact
        )
        with self.assertRaises(NinjaValidationError) as cm:
            delete_with_form(
                project, _request(project.owned_by), loc=["path"], dry_run=False
            )
        self.assertEqual([error["loc"] for error in _errors(cm)], [["path"]])
        self.assertIn("because of related objects", _errors(cm)[0]["msg"])


class PatchWithFormTest(TestCase):
    def test_patch(self):
        """Fields are renamed and converted, errors are located at the API
        field, dry runs return the result and change nothing"""
        project = factories.ProjectFactory.create(title="Before")
        request = _request(project.owned_by)
        field_map = {"name": "title", "owner": ("owned_by", active_user)}

        def patch(data, **kwargs):
            return patch_with_form(
                ProjectForm,
                project,
                data,
                request,
                out=lambda project: (project.title, project.owned_by_id),
                field_map=field_map,
                **kwargs,
            )

        inactive = factories.UserFactory.create(is_active=False)
        with self.assertRaises(NinjaValidationError) as cm:
            patch({"owner": inactive.get_short_name()})
        self.assertEqual(
            [error["loc"] for error in _errors(cm)], [["body", "data", "owner"]]
        )

        with self.assertRaises(NinjaValidationError) as cm:
            patch({"name": None})
        self.assertEqual(
            [error["loc"] for error in _errors(cm)], [["body", "data", "name"]]
        )

        user = factories.UserFactory.create()
        self.assertEqual(
            patch({"name": "After", "owner": user.get_short_name()}, dry_run=True),
            ("After", user.pk),
        )
        project.refresh_from_db()
        self.assertEqual(project.title, "Before")

        patch({"name": "After"})
        project.refresh_from_db()
        self.assertEqual((project.title, project.owned_by), ("After", request.user))

    def test_converters(self):
        self.assertEqual(api_key("deal_probability")("high"), Deal.HIGH)
        with self.assertRaises(ValidationError):
            api_key("deal_probability")("maybe")

        project = factories.ProjectFactory.create()
        convert = object_pk(Project.objects.all())
        self.assertEqual(convert(project.pk), project.pk)
        self.assertEqual(convert(project.code), project.pk)
        with self.assertRaises(ValidationError):
            convert(project.pk + 1)
