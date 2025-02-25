from django import forms
from django.conf import settings
from django.contrib import messages
from django.forms.models import inlineformset_factory
from django.utils.html import format_html
from django.utils.text import capfirst
from django.utils.translation import gettext, gettext_lazy as _, override

from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.contacts.models import Organization, Person
from workbench.invoices.models import ProjectedInvoice
from workbench.projects.models import Campaign, Project, Service
from workbench.reporting.models import FreezeDate
from workbench.services.models import ServiceType
from workbench.tools.formats import local_date_format
from workbench.tools.forms import (
    Autocomplete,
    DateInput,
    Form,
    ModelForm,
    Textarea,
    add_prefix,
)
from workbench.tools.validation import in_days, is_title_specific


class CampaignSearchForm(Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Search")}
        ),
        label="",
    )
    s = forms.ChoiceField(
        choices=[
            ("all", _("All")),
            (capfirst(_("status")), [("", _("Open")), ("closed", _("Closed"))]),
        ],
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
        if not data.get("s"):
            queryset = queryset.open()
        elif data.get("s") == "closed":
            queryset = queryset.closed()
        queryset = self.apply_renamed(queryset, "org", "customer")
        queryset = self.apply_simple(queryset, "type")
        queryset = self.apply_owned_by(queryset)
        return queryset.select_related("customer", "owned_by")


class CampaignForm(ModelForm):
    user_fields = default_to_current_user = ("owned_by",)

    class Meta:
        model = Campaign
        fields = (
            "customer",
            "title",
            "description",
            "owned_by",
        )
        widgets = {
            "customer": Autocomplete(model=Organization, plus=True),
            "description": Textarea,
        }

    def __init__(self, *args, **kwargs):
        initial = kwargs.setdefault("initial", {})
        request = kwargs["request"]

        if pk := request.GET.get("copy"):
            try:
                campaign = Campaign.objects.get(pk=pk)
            except (Campaign.DoesNotExist, TypeError, ValueError):
                pass
            else:
                initial.update({
                    "customer": campaign.customer_id,
                    "title": campaign.title,
                    "description": campaign.description,
                    "owned_by": (
                        campaign.owned_by_id
                        if campaign.owned_by.is_active
                        else request.user.id
                    ),
                })

        elif pk := request.GET.get("customer"):
            try:
                customer = Organization.objects.get(pk=pk)
            except (Organization.DoesNotExist, TypeError, ValueError):
                pass
            else:
                initial.update({"customer": customer})

        super().__init__(*args, **kwargs)


class CampaignDeleteForm(ModelForm):
    class Meta:
        model = Campaign
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.projects.exists():
            self.add_warning(
                _(
                    "Projects are linked with this campaign."
                    " They will be released when deleting this campaign."
                ),
                code="release-projects",
            )

    def delete(self):
        self.instance.projects.update(campaign=None)
        self.instance.delete()


class ProjectSearchForm(Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Search")}
        ),
        label="",
    )
    s = forms.ChoiceField(
        choices=[
            ("all", _("All")),
            (capfirst(_("status")), [("", _("Open")), ("closed", _("Closed"))]),
            (
                _("Defined search"),
                [
                    ("no-invoices", _("No invoices")),
                    ("accepted-offers", _("Accepted offers")),
                    (
                        "accepted-offers-no-invoices",
                        _("Accepted offers but no invoices"),
                    ),
                    ("solely-declined-offers", _("Solely declined offers")),
                    ("old-projects", _("Old projects (60 days inactivity)")),
                    ("empty-logbook", _("Empty logbook")),
                    (
                        "invalid-customer-contact-combination",
                        _("Invalid customer/contact combination"),
                    ),
                    (
                        "no-projected-gross-margin",
                        _("No projected gross margin"),
                    ),
                ],
            ),
        ],
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
    type = forms.ChoiceField(
        choices=[("", _("All types")), *Project.TYPE_CHOICES],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
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
        if not data.get("s"):
            queryset = queryset.open()
        elif data.get("s") == "closed":
            queryset = queryset.closed()
        elif data.get("s") == "no-invoices":
            queryset = queryset.orders().without_invoices().open()
        elif data.get("s") == "accepted-offers":
            queryset = queryset.with_accepted_offers()
        elif data.get("s") == "accepted-offers-no-invoices":
            queryset = queryset.with_accepted_offers().without_invoices().open()
        elif data.get("s") == "solely-declined-offers":
            queryset = queryset.solely_declined_offers()
        elif data.get("s") == "old-projects":
            queryset = queryset.old_projects()
        elif data.get("s") == "empty-logbook":
            queryset = queryset.empty_logbook()
        elif data.get("s") == "invalid-customer-contact-combination":
            queryset = queryset.invalid_customer_contact_combination()
        elif data.get("s") == "no-projected-gross-margin":
            queryset = queryset.no_projected_gross_margin()
        queryset = self.apply_renamed(queryset, "org", "customer")
        queryset = self.apply_simple(queryset, "type")
        queryset = self.apply_owned_by(queryset)
        return queryset.select_related("customer", "contact__organization", "owned_by")


class ProjectForm(ModelForm):
    user_fields = default_to_current_user = ("owned_by",)

    class Meta:
        model = Project
        fields = (
            "contact",
            "customer",
            "title",
            "description",
            "campaign",
            "cost_center",
            "owned_by",
            "type",
            "internal_type",
            "suppress_planning_update_mails",
            "flat_rate",
            "closed_on",
        )
        widgets = {
            "customer": Autocomplete(model=Organization, plus=True),
            "contact": Autocomplete(
                model=Person, params={"only_employees": "on"}, plus=True
            ),
            "campaign": Autocomplete(model=Campaign),
            "description": Textarea,
            "type": forms.RadioSelect,
            "internal_type": forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):  # noqa: C901
        initial = kwargs.setdefault("initial", {})
        request = kwargs["request"]

        if pk := request.GET.get("copy"):
            try:
                project = Project.objects.get(pk=pk)
            except (Project.DoesNotExist, TypeError, ValueError):
                pass
            else:
                initial.update({
                    "customer": project.customer_id,
                    "contact": project.contact_id,
                    "title": project.title,
                    "description": project.description,
                    "type": project.type,
                    "internal_type": project.internal_type_id,
                    "flat_rate": project.flat_rate,
                    "owned_by": (
                        project.owned_by_id
                        if project.owned_by.is_active
                        else request.user.id
                    ),
                })

        elif pk := request.GET.get("contact"):
            try:
                contact = Person.objects.get(pk=pk)
            except (Person.DoesNotExist, TypeError, ValueError):
                pass
            else:
                initial.update({"customer": contact.organization, "contact": contact})

        elif pk := request.GET.get("customer"):
            try:
                customer = Organization.objects.get(pk=pk)
            except (Organization.DoesNotExist, TypeError, ValueError):
                pass
            else:
                initial.update({"customer": customer})

        for field in ["cost_center", "campaign"]:
            if value := request.GET.get(field):
                initial[field] = value

        super().__init__(*args, **kwargs)
        self.fields["type"].choices = [
            (Project.ORDER, _("Order")),
            (
                Project.MAINTENANCE,
                _("Maintenance (normally fully chargeable, no cost ceiling)"),
            ),
            (Project.INTERNAL, _("Internal")),
        ]
        self.fields["internal_type"].empty_label = _("Not internal")
        if not self.request.user.features[FEATURES.INTERNAL_TYPES]:
            self.fields.pop("internal_type")
        if not self.request.user.features[FEATURES.CONTROLLING]:
            self.fields.pop("flat_rate")
        if not self.request.user.features[FEATURES.CAMPAIGNS]:
            self.fields.pop("campaign")
        if not self.request.user.features[FEATURES.LABOR_COSTS]:
            self.fields.pop("cost_center")
        if not self.request.user.features[FEATURES.PLANNING]:
            self.fields.pop("suppress_planning_update_mails")
        if self.instance.pk:
            self.fields["closed_on"].help_text = format_html(
                '{} <a href="#" data-field-value="{}">{}</a>',
                _("Set predefined value:"),
                in_days(0).isoformat(),
                _("today"),
            )
            if (
                self.instance.closed_on
                and (freeze := FreezeDate.objects.up_to())
                and self.instance.closed_on <= freeze
            ):
                if self.request.method == "GET":
                    messages.warning(
                        self.request,
                        _(
                            "This project has been closed on or before {} and cannot be reopened anymore."
                        ).format(local_date_format(freeze)),
                    )
                self.fields["closed_on"].disabled = True
        else:
            self.fields.pop("closed_on")

    def clean(self):
        data = super().clean()

        if (
            self.request.user.features[FEATURES.INTERNAL_TYPES]
            and data.get("type") == Project.INTERNAL
            and not data.get("internal_type")
        ):
            self.add_error(
                "internal_type",
                _("Selecting an internal type is required for internal projects."),
            )
        elif (
            self.request.user.features[FEATURES.INTERNAL_TYPES]
            and data.get("type") != Project.INTERNAL
            and data.get("internal_type")
        ):
            self.add_error(
                "internal_type",
                _("The internal type must not be set when project is not internal."),
            )

        if (
            set(self.changed_data) & {"customer"}
            and self.instance.pk
            and self.instance.invoices.exists()
        ):
            self.add_warning(
                _(
                    "This project already has invoices. The invoices'"
                    " customer record will be changed too."
                ),
                code="customer-update-but-already-invoices",
            )

        if (
            set(self.changed_data) & {"flat_rate"}
            and data.get("flat_rate") is not None
            and self.instance.pk
            and self.instance.services.exists()
        ):
            self.add_warning(
                _(
                    "You are adding a flat rate to a project which already"
                    " has services. Those services' effort types and rates"
                    " will be overwritten."
                ),
                code="flat-rate-but-already-services",
            )

        if (
            set(self.changed_data) & {"closed_on"}
            and (closed_on := data.get("closed_on"))
            and (freeze := FreezeDate.objects.up_to())
            and closed_on <= freeze
        ):
            self.add_error(
                "closed_on",
                _(
                    "Cannot close a project with a date of {} or earlier anymore."
                ).format(local_date_format(freeze)),
            )

        return data

    def save(self):
        instance = super().save(commit=False)
        if self.instance.pk and self.instance.flat_rate is not None:
            with override(settings.WORKBENCH.PDF_LANGUAGE):
                for service in self.instance.services.editable():
                    service.effort_type = gettext("flat rate")
                    service.effort_rate = self.instance.flat_rate
                    service.save(skip_related_model=True)
        instance.save()
        if "customer" in self.changed_data:
            instance.invoices.update(customer=instance.customer)
        return instance


class ServiceForm(ModelForm):
    service_type = forms.ModelChoiceField(
        ServiceType.objects.all(),
        label=ServiceType._meta.verbose_name,
        required=False,
        help_text=_("Optional, but useful for quickly filling the fields below."),
    )

    class Meta:
        model = Service
        fields = [
            "title",
            "description",
            "allow_logging",
            "offer",
            "is_optional",
            "effort_type",
            "effort_hours",
            "effort_rate",
            "cost",
            "third_party_costs",
        ]
        widgets = {"description": Textarea()}

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project", None)
        if not self.project:
            self.project = kwargs["instance"].project
        elif self.project.flat_rate is not None:
            with override(settings.WORKBENCH.PDF_LANGUAGE):
                kwargs["instance"] = Service(
                    effort_type=gettext("flat rate"), effort_rate=self.project.flat_rate
                )

        super().__init__(*args, **kwargs)

        self.fields["offer"].choices = self.project.offers.service_form_choices(
            include=getattr(self.instance, "offer_id", None)
        )
        self.instance.project = self.project

        offer = self.instance.offer
        if offer and offer.status > offer.SERVICE_GROUP:
            for field in self.fields:
                if field != "allow_logging":
                    self.fields[field].disabled = True

            if self.request.method == "GET":
                messages.warning(
                    self.request,
                    _(
                        "Most fields are disabled because service is bound"
                        " to an offer which is not in preparation anymore."
                    ),
                )

        if self.project.flat_rate is not None:
            self.fields["effort_type"].disabled = True
            self.fields["effort_rate"].disabled = True
            self.fields.pop("service_type")

    def clean(self):
        data = super().clean()
        if data.get("title") and not is_title_specific(data["title"]):
            self.add_warning(
                _(
                    "This title seems awfully unspecific."
                    " Please use specific titles for services."
                ),
                code="unspecific-service",
            )
        return data


class ReassignLogbookForm(Form):
    service = forms.ModelChoiceField(
        Service.objects.all(), label=Service._meta.verbose_name
    )

    def __init__(self, *args, **kwargs):
        self.from_service = kwargs.pop("instance")
        super().__init__(*args, **kwargs)
        self.fields[
            "service"
        ].queryset = self.from_service.project.services.logging().exclude(
            pk=self.from_service.pk
        )

        offer = self.from_service.offer
        if not offer or offer.status <= offer.IN_PREPARATION:
            self.fields["try_delete"] = forms.BooleanField(
                label=_("Try deleting the service after reassigning logbook entries"),
                required=False,
            )

    def save(self):
        service = self.cleaned_data["service"]
        self.from_service.loggedhours.update(service=service)
        self.from_service.loggedcosts.update(service=service)

        if self.cleaned_data.get("try_delete") and self.from_service.allow_delete(
            self.from_service, self.request
        ):
            self.from_service.delete()
            messages.success(
                self.request,
                _("%(class)s '%(object)s' has been deleted successfully.")
                % {
                    "class": self.from_service._meta.verbose_name,
                    "object": self.from_service,
                },
            )
        return service


@add_prefix("modal")
class ServiceMoveForm(ModelForm):
    class Meta:
        model = Service
        fields = ["project"]
        widgets = {"project": Autocomplete(model=Project, params={"only_open": "on"})}

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("initial", {}).setdefault("project", "")
        super().__init__(*args, **kwargs)

        if self.instance.offer and self.request.method == "GET":
            messages.error(
                self.request,
                _("Cannot move a service which is already bound to an offer."),
            )

    def clean(self):
        data = super().clean()
        if data.get("project") and data.get("project").closed_on:
            self.add_error("project", _("This project is already closed."))

        if (
            data.get("project")
            and self.instance.project.flat_rate is None
            and data["project"].flat_rate is not None
        ):
            self.add_warning(
                _(
                    "The project %(project)s has a flat rate which will be applied"
                    " to this service too."
                )
                % {"project": data["project"]},
                code="new-project-has-flat-rate",
            )
        return data

    def save(self):
        instance = super().save(commit=False)
        if instance.project.flat_rate is not None:
            instance.effort_type = gettext("flat rate")
            instance.effort_rate = instance.project.flat_rate
        instance.save()
        return instance


@add_prefix("modal")
class ProjectAutocompleteForm(forms.Form):
    project = forms.ModelChoiceField(
        queryset=Project.objects.all(),
        widget=Autocomplete(model=Project, params={"only_open": "on"}),
        label="",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        logging = kwargs.pop("logging", False)
        super().__init__(*args, **kwargs)
        self.fields["service"] = forms.ModelChoiceField(
            queryset=Service.objects.all(),
            widget=Autocomplete(
                model=Service, params={"logging": "on" if logging else ""}
            ),
            label="",
            required=False,
        )

    def clean(self):
        data = super().clean()
        if data["service"]:
            data["project"] = data["service"].project
            return data
        if data["project"]:
            return data
        self.add_error("project", _("This field is required."))
        return data


class OffersRenumberForm(Form):
    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("instance")

        super().__init__(*args, **kwargs)

        self.offers = self.project.offers.order_by("_code")
        for offer in self.offers:
            self.fields[f"offer_{offer.pk}_code"] = forms.IntegerField(
                label=str(offer),
                initial=offer._code,
                min_value=1,
            )

    def clean(self):
        data = super().clean()
        self.codes = {
            offer: data.get(f"offer_{offer.pk}_code") for offer in self.offers
        }
        if len(self.codes) != len(set(self.codes.values())):
            raise forms.ValidationError(_("Codes must be unique."))
        return data

    def save(self):
        for offer, code in self.codes.items():
            offer._code = code
            offer.save()
        return self.project


ProjectedInvoiceFormset = inlineformset_factory(
    Project,
    ProjectedInvoice,
    fields=["invoiced_on", "gross_margin", "description"],
    extra=0,
    widgets={
        "invoiced_on": DateInput,
    },
)


class ProjectedInvoicesProjectForm(ModelForm):
    class Meta:
        model = Project
        fields = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        kwargs.pop("request")
        self.formsets = {
            "projected_invoices": ProjectedInvoiceFormset(*args, **kwargs),
        }

    def is_valid(self):
        return all(
            [super().is_valid()]
            + [formset.is_valid() for formset in self.formsets.values()]
        )

    def save(self, *, commit=True):
        instance = super().save()
        for formset in self.formsets.values():
            formset.save()
        return instance
