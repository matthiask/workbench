from django import forms
from django.conf import settings
from django.contrib import messages
from django.utils.text import capfirst
from django.utils.translation import gettext, gettext_lazy as _, override

from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.circles.models import Role
from workbench.contacts.models import Organization, Person
from workbench.projects.models import Project, Service
from workbench.services.models import ServiceType
from workbench.tools.forms import Autocomplete, Form, ModelForm, Textarea, add_prefix


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
                    ("old-projects", _("Old projects (60 days inactivity)")),
                    (
                        "invalid-customer-contact-combination",
                        _("Invalid customer/contact combination"),
                    ),
                ],
            ),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )
    org = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        required=False,
        widget=Autocomplete(model=Organization),
        label="",
    )
    type = forms.ChoiceField(
        choices=[("", _("All types"))] + Project.TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )
    owned_by = forms.TypedChoiceField(
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
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
        if data.get("s") == "":
            queryset = queryset.open()
        elif data.get("s") == "closed":
            queryset = queryset.closed()
        elif data.get("s") == "no-invoices":
            queryset = queryset.orders().without_invoices()
        elif data.get("s") == "accepted-offers":
            queryset = queryset.with_accepted_offers()
        elif data.get("s") == "accepted-offers-no-invoices":
            queryset = queryset.with_accepted_offers().without_invoices()
        elif data.get("s") == "old-projects":
            queryset = queryset.old_projects()
        elif data.get("s") == "invalid-customer-contact-combination":
            queryset = queryset.invalid_customer_contact_combination()
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
            "cost_center",
            "owned_by",
            "type",
            "flat_rate",
            "closed_on",
        )
        widgets = {
            "customer": Autocomplete(model=Organization),
            "contact": Autocomplete(model=Person),
            "description": Textarea,
            "type": forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        initial = kwargs.setdefault("initial", {})
        request = kwargs["request"]

        if request.GET.get("copy"):
            try:
                project = Project.objects.get(pk=request.GET["copy"])
            except (Project.DoesNotExist, TypeError, ValueError):
                pass
            else:
                initial.update(
                    {
                        "customer": project.customer_id,
                        "contact": project.contact_id,
                        "title": project.title,
                        "description": project.description,
                        "type": project.type,
                        "owned_by": (
                            project.owned_by_id if project.owned_by.is_active else None
                        ),
                    }
                )

        super().__init__(*args, **kwargs)
        self.fields["type"].choices = Project.TYPE_CHOICES
        if not self.request.user.features[FEATURES.CONTROLLING]:
            self.fields.pop("flat_rate")
        if not self.request.user.features[FEATURES.LABOR_COSTS]:
            self.fields.pop("cost_center")
        if not self.instance.pk:
            self.fields.pop("closed_on")

    def clean(self):
        data = super().clean()

        if set(self.changed_data) & {"customer"} and self.instance.invoices.exists():
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

        return data

    def save(self):
        instance = super().save(commit=False)
        if self.instance.flat_rate is not None:
            with override(settings.WORKBENCH.PDF_LANGUAGE):
                self.instance.services.editable().update(
                    effort_type=gettext("flat rate"),
                    effort_rate=self.instance.flat_rate,
                )
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
            "role",
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

        self.fields["role"].choices = Role.objects.choices()
        self.fields["offer"].choices = self.project.offers.in_preparation_choices(
            include=getattr(self.instance, "offer_id", None)
        )
        self.instance.project = self.project

        offer = self.instance.offer
        if offer and offer.status > offer.IN_PREPARATION:
            for field in self.fields:
                if field not in {"role", "allow_logging"}:
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

        if not self.request.user.features[FEATURES.GLASSFROG]:
            self.fields.pop("role")

    def clean(self):
        data = super().clean()
        if self.request.user.features[FEATURES.GLASSFROG] and not data.get("role"):
            self.add_warning(_("No role selected."), code="no-role-selected")
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


class ServiceMoveForm(ModelForm):
    class Meta:
        model = Service
        fields = ["project"]
        widgets = {"project": Autocomplete(model=Project)}

    def clean(self):
        data = super().clean()
        if data.get("project") and data.get("project").closed_on:
            self.add_error("project", _("This project is already closed."))
        return data


@add_prefix("modal")
class ProjectAutocompleteForm(forms.Form):
    project = forms.ModelChoiceField(
        queryset=Project.objects.all(),
        widget=Autocomplete(model=Project, params={"only_open": "on"}),
        label="",
    )


class OffersRenumberForm(Form):
    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("instance")

        super().__init__(*args, **kwargs)

        self.offers = self.project.offers.order_by("_code")
        for offer in self.offers:
            self.fields["offer_{}_code".format(offer.pk)] = forms.IntegerField(
                label=str(offer), initial=offer._code, min_value=1,
            )

    def clean(self):
        data = super().clean()
        self.codes = {
            offer: data.get("offer_{}_code".format(offer.pk)) for offer in self.offers
        }
        if len(self.codes) != len(set(self.codes.values())):
            raise forms.ValidationError(_("Codes must be unique."))
        return data

    def save(self):
        for offer, code in self.codes.items():
            offer._code = code
            offer.save()
        return self.project
