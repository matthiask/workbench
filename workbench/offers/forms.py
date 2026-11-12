import datetime as dt

from django import forms
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.forms.models import BaseInlineFormSet, inlineformset_factory
from django.utils.translation import gettext, gettext_lazy as _, override

from workbench.accounts.models import User
from workbench.contacts.forms import PostalAddressSelectionForm
from workbench.contacts.models import Organization
from workbench.offers.models import Offer, OfferHeading
from workbench.projects.models import Project, Service
from workbench.services.models import ServiceType
from workbench.tools.formats import local_date_format
from workbench.tools.forms import (
    Autocomplete,
    Form,
    ModelForm,
    Textarea,
    add_prefix,
    delete_planned_work_field,
)
from workbench.tools.models import ProtectedError, SlowCollector


class OfferSearchForm(Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Search")}
        ),
        label="",
    )
    s = forms.ChoiceField(
        choices=(
            ("all", _("All states")),
            ("", _("Open")),
            (_("Exact"), Offer.STATUS_CHOICES),
        ),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )
    org = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        required=False,
        widget=Autocomplete(model=Organization),
        label="",
    )
    owned_by = forms.TypedChoiceField(
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owned_by"].choices = User.objects.choices(
            collapse_inactive=True, myself=True
        )

    def filter(self, queryset):
        data = self.cleaned_data
        queryset = queryset.search(data.get("q"))
        if data.get("s") == "all":
            pass
        elif data.get("s"):
            queryset = queryset.filter(status=data.get("s"))
        else:
            queryset = queryset.filter(
                project__closed_on__isnull=True,
                status__in=(Offer.IN_PREPARATION, Offer.OFFERED),
            )
        queryset = self.apply_renamed(queryset, "org", "project__customer")
        queryset = self.apply_owned_by(queryset)
        return queryset.select_related(
            "owned_by",
            "project__owned_by",
            "project__customer",
            "project__contact__organization",
        )


def warn_if_not_in_preparation(form):
    if (
        form.instance.pk
        and form.instance.status >= form.instance.OFFERED
        and form.request.method == "GET"
    ):
        messages.warning(
            form.request,
            _(
                "This offer is not in preparation anymore. Put it back into"
                " preparation to change its services."
            ),
        )


class OfferForm(PostalAddressSelectionForm):
    user_fields = default_to_current_user = ("owned_by",)

    class Meta:
        model = Offer
        fields = (
            "offered_on",
            "valid_until",
            "title",
            "description",
            "owned_by",
            "status",
            "postal_address",
            "subtotal",
            "discount",
            "liable_to_vat",
            "tax_rate",
            "show_service_details",
            "work_completed_on",
            "is_budget_retainer",
            "external_reference",
        )
        widgets = {
            "description": Textarea({"rows": 2, "class": "wb-autogrow"}),
            "external_reference": Textarea({"rows": 1, "class": "wb-autogrow"}),
            "status": forms.RadioSelect,
            "postal_address": Textarea,
            "tax_rate": forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project", None)
        if self.project:  # Creating a new offer
            kwargs.setdefault("initial", {}).update({"title": self.project.title})
        else:
            self.project = kwargs["instance"].project

        super().__init__(*args, **kwargs)
        warn_if_not_in_preparation(self)

        self.instance.project = self.project
        # Services of offers which have been sent stay as they were sent
        self.services_changeable = self.instance.services_changeable
        self.formsets = {
            "services": ServiceFormset(
                self.data or None,
                instance=self.instance,
                form_kwargs={
                    "offer": self.instance,
                    "editable": self.services_changeable,
                },
            ),
            "headings": HeadingFormset(
                self.data or None,
                instance=self.instance,
                form_kwargs={"editable": self.services_changeable},
            ),
        }

        self.order_fields(
            field
            for field in list(self.fields)
            if field
            not in {
                "subtotal",
                "discount",
                "liable_to_vat",
                "tax_rate",
                "show_service_details",
                "work_completed_on",
                "is_budget_retainer",
            }
        )

        self.add_postal_address_selection_if_empty(
            person=self.project.contact, organization=self.project.customer
        )
        self.fields["subtotal"].disabled = True
        self.fields["discount"].widget.attrs["class"] = "form-control text-end"

        if self.instance.pk and self.instance.planned_work.all().after_this_week():
            posted_status = (
                self.data.get(self.add_prefix("status")) if self.is_bound else None
            )
            status = posted_status or str(self.instance.status)
            if status == str(Offer.DECLINED):
                self.fields["delete_planned_work"] = delete_planned_work_field(
                    _(
                        "This offer has planning entries after the current"
                        " week linked to it. Delete them now that the offer is"
                        " being declined?"
                    )
                )
            elif status == str(Offer.DISCARDED):
                self.fields["delete_planned_work"] = delete_planned_work_field(
                    _(
                        "This offer has planning entries after the current"
                        " week linked to it. Delete them now that the offer is"
                        " being discarded?"
                    )
                )

    def clean_work_completed_on(self):
        # Prohibits logging right away, a future date makes no sense
        value = self.cleaned_data.get("work_completed_on")
        if value and value > dt.date.today():
            raise forms.ValidationError(_("Work cannot be completed in the future."))
        return value

    def clean(self):
        data = super().clean()
        s_dict = dict(Offer.STATUS_CHOICES)

        if not self.instance.pk and self.project.closed_on:
            raise forms.ValidationError(_("The project is closed."))

        if self.instance.closed_on and data["status"] < Offer.ACCEPTED:
            self.add_warning(
                _(
                    "You are attempting to set status to '%(to)s',"
                    " but the offer has already been closed on %(closed)s."
                    " Are you sure?"
                )
                % {
                    "to": s_dict[data["status"]],
                    "closed": local_date_format(self.instance.closed_on),
                },
                code="status-change-but-already-closed",
            )

        if data["status"] == Offer.DECLINED:
            self.add_warning(
                _(
                    "You are setting the offer status to 'Declined'."
                    " However, if you just want to change a few things"
                    " and send the offer to the client again then you"
                    " could just as well put the offer back into preparation."
                ),
                code="yes-please-decline",
            )

        # Retainers are released with services without offer: other offers
        # are added to them
        others = (
            self.project.offers
            .exclude(pk=self.instance.pk)
            .exclude(status__in=Offer.NOT_PURSUED)
            .values_list("is_budget_retainer", flat=True)
        )
        if (
            data.get("is_budget_retainer")
            and not self.instance.is_budget_retainer
            and False in others
        ):
            self.add_warning(
                _(
                    "This project has other offers. They are added to the"
                    " budget retainer, release the retained budget with"
                    " services without offer."
                ),
                code="budget-retainer",
            )
        elif (
            not self.instance.pk
            and not data.get("is_budget_retainer")
            and True in others
        ):
            self.add_warning(
                _(
                    "This project has a budget retainer. This offer is added"
                    " to it, release the retained budget with services without"
                    " offer instead."
                ),
                code="budget-retainer",
            )

        return data

    def total_titles(self):
        """Titles of the totals with and without tax, the form switches
        between them"""
        currency = {"currency": settings.WORKBENCH.CURRENCY}
        return {
            "total": _("Total %(currency)s") % currency,
            "total_incl_tax": _("Total %(currency)s incl. tax") % currency,
            "optional": _("Total %(currency)s for optional services") % currency,
            "optional_excl_tax": (
                _("Total %(currency)s excl. tax for optional services") % currency
            ),
        }

    def rows(self):
        """The forms of services and headings in the order they're shown
        (the services without offer are hidden rows)"""

        def position(form):
            try:
                return int(form["position"].value())
            except TypeError, ValueError:
                return 0

        return sorted(
            [
                *(("heading", form) for form in self.formsets["headings"]),
                *(("service", form) for form in self.formsets["services"]),
            ],
            key=lambda row: (position(row[1]), row[0] == "service"),
        )

    def is_valid(self):
        return all([
            super().is_valid(),
            *(
                formset.is_valid()
                for formset in self.formsets.values()
                if self.services_changeable
            ),
        ])

    def save(self):
        instance = super().save(commit=False)
        if not instance.pk:
            instance.save()
        if self.services_changeable:
            for formset in self.formsets.values():
                formset.save()
        # Totals of the services
        instance.save()
        if instance.status in Offer.NOT_PURSUED and self.cleaned_data.get(
            "delete_planned_work"
        ):
            instance.planned_work.all().delete_after_this_week()
        instance.project.solely_declined_offers_warning(request=self.request)
        return instance


class ServiceForm(forms.ModelForm):
    """A service in the offer form: the offer's services and the project's
    services without offer, which can be added to the offer"""

    service_type = forms.ModelChoiceField(
        ServiceType.objects.all(),
        label=ServiceType._meta.verbose_name,
        required=False,
    )
    in_offer = forms.BooleanField(
        required=False, widget=forms.CheckboxInput(attrs={"hidden": True})
    )

    class Meta:
        model = Service
        fields = "__all__"  # noqa: DJ007

    def __init__(self, *args, offer, editable, **kwargs):
        super().__init__(*args, **kwargs)
        self.offer = offer
        project = offer.project
        # Unchanged services aren't validated, those without offer are hidden
        self.empty_permitted = True
        self.initial["in_offer"] = not self.instance.pk or bool(
            offer.pk and self.instance.offer_id == offer.pk
        )
        # New services are added at the end unless they are moved
        self.fields["position"].required = False
        if not self.instance.pk:
            self.instance.project = project
            if project.flat_rate is not None:
                with override(settings.WORKBENCH.PDF_LANGUAGE):
                    self.initial["effort_type"] = gettext("flat rate")
                self.initial["effort_rate"] = project.flat_rate

        # Invoiced services keep their effort type and rate, the logbook of
        # invoiced work would be valued differently
        if not editable or project.flat_rate is not None or self.instance.is_invoiced:
            self.fields["effort_type"].disabled = True
            self.fields["effort_rate"].disabled = True
            self.fields.pop("service_type")
        if not editable:
            for field in self.fields.values():
                field.disabled = True

    def clean_position(self):
        # Services without position are added at the end when saving
        return self.cleaned_data.get("position") or 0

    def has_changed(self):
        if not self.instance.pk:
            # Empty new rows are skipped, also when they have been moved, and
            # so are removed ones
            return bool(
                self["in_offer"].data
                and set(self.changed_data) - {"position", "in_offer"}
            )
        return super().has_changed()

    def save(self, commit=True):  # noqa: FBT002
        instance = super().save(commit=False)
        instance.offer = self.offer if self.cleaned_data["in_offer"] else None
        instance.save(skip_related_model=True)
        return instance


class ServiceFormsetBase(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Before validating the offer changes its status
        self.get_queryset()

    def get_queryset(self):
        if not hasattr(self, "_queryset"):
            services = Service.objects.filter(project=self.instance.project)
            if self.instance.pk:
                offer = Q(offer=self.instance)
                if self.instance.services_changeable:
                    offer |= Q(offer__isnull=True)
                services = services.filter(offer)
            elif self.instance.services_changeable:
                services = services.filter(offer__isnull=True)
            else:
                services = services.none()
            self._queryset = services.select_related("project")
        return self._queryset


class HeadingForm(forms.ModelForm):
    class Meta:
        model = OfferHeading
        fields = ["position", "title", "description"]
        widgets = {
            "position": forms.HiddenInput,
            "description": Textarea({"rows": 1, "class": "wb-autogrow"}),
        }

    def __init__(self, *args, editable, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["position"].required = False
        if not editable:
            for field in self.fields.values():
                field.disabled = True

    def has_changed(self):
        if not self.instance.pk:
            # Empty new rows are skipped, also when they have been moved
            return bool(set(self.changed_data) - {"position"})
        return super().has_changed()

    def clean_position(self):
        return self.cleaned_data.get("position") or 0


HeadingFormset = inlineformset_factory(
    Offer, OfferHeading, form=HeadingForm, extra=0, can_delete=True
)


ServiceFormset = inlineformset_factory(
    Offer,
    Service,
    form=ServiceForm,
    formset=ServiceFormsetBase,
    fields=(
        "position",
        "title",
        "description",
        "effort_type",
        "effort_rate",
        "effort_hours",
        "cost",
        "is_optional",
    ),
    widgets={
        "position": forms.HiddenInput,
        "description": Textarea({"rows": 1, "class": "wb-autogrow"}),
    },
    extra=0,
    can_delete=False,
)


@add_prefix("modal")
class OfferCopyForm(Form):
    project = forms.ModelChoiceField(
        queryset=Project.objects.open(),
        widget=Autocomplete(model=Project, params={"only_open": "on"}),
        label="",
    )

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project")
        super().__init__(*args, **kwargs)

    def clean_project(self):
        project = self.cleaned_data.get("project")
        if project == self.project:
            self.add_warning(
                _("Same project selected as offer already belongs to."),
                code="same-project",
            )
        return project


class OfferDeleteForm(ModelForm):
    class Meta:
        model = Offer
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        collector = SlowCollector(using=self.instance._state.db)
        try:
            collector.collect(self.instance.services.all())
        except ProtectedError:
            pass
        else:
            # Invoice lines point to invoiced services, they stay
            if not any(service.is_invoiced for service in self.instance.services.all()):
                self.fields["delete_services"] = forms.BooleanField(
                    label=_("Delete offers' services?"), required=False
                )

        if self.instance.planned_work.exists():
            self.fields["delete_planned_work"] = forms.BooleanField(
                label=_("Delete planned work linked to offer?"), required=True
            )

    def delete(self):
        if self.cleaned_data.get("delete_services"):
            self.instance.services.all().delete()
        if self.cleaned_data.get("delete_planned_work"):
            self.instance.planned_work.all().delete()
        self.instance.delete()
