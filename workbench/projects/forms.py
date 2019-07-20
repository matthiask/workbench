from datetime import date

from django import forms
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.circles.models import Role
from workbench.contacts.models import Organization, Person
from workbench.projects.models import Project, Service
from workbench.services.models import ServiceType
from workbench.tools.forms import Autocomplete, ModelForm, Textarea


class ProjectSearchForm(forms.Form):
    s = forms.ChoiceField(
        choices=(("all", _("All states")), ("", _("Open")), ("closed", _("Closed"))),
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
        self.fields["owned_by"].choices = User.objects.choices(collapse_inactive=True)

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("s") == "":
            queryset = queryset.filter(closed_on__isnull=True)
        elif data.get("s") == "closed":
            queryset = queryset.filter(closed_on__isnull=False)
        if data.get("org"):
            queryset = queryset.filter(customer=data.get("org"))
        if data.get("type"):
            queryset = queryset.filter(type=data.get("type"))
        if data.get("owned_by") == 0:
            queryset = queryset.filter(owned_by__is_active=False)
        elif data.get("owned_by"):
            queryset = queryset.filter(owned_by=data.get("owned_by"))

        return queryset.select_related("customer", "contact__organization", "owned_by")


class ProjectForm(ModelForm):
    user_fields = default_to_current_user = ("owned_by",)

    class Meta:
        model = Project
        fields = ("customer", "contact", "title", "description", "owned_by", "type")
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
        if self.instance.pk:
            self.fields["is_closed"] = forms.BooleanField(
                label=_("is closed"),
                required=False,
                initial=bool(self.instance.closed_on),
            )

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

        return data

    def save(self):
        instance = super().save(commit=False)
        if not instance.closed_on and self.cleaned_data.get("is_closed"):
            instance.closed_on = date.today()
        if instance.closed_on and not self.cleaned_data.get("is_closed"):
            instance.closed_on = None
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


class ServiceDeleteForm(ModelForm):
    class Meta:
        model = Service
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.loggedhours.exists() or self.instance.loggedcosts.exists():
            queryset = self.instance.project.services.logging().exclude(
                pk=self.instance.pk
            )
            self.fields["merge_into"] = forms.ModelChoiceField(
                queryset=queryset, label=_("Merge log into")
            )
            self.fields["merge_into"].choices = queryset.choices()

    def delete(self):
        if "merge_into" not in self.cleaned_data:
            self.instance.delete()
            return self.instance

        into = self.cleaned_data["merge_into"]
        self.instance.loggedhours.update(service=into)
        self.instance.loggedcosts.update(service=into)
        self.instance.delete()
        return into


class ServiceMoveForm(ModelForm):
    class Meta:
        model = Service
        fields = ["project"]
        widgets = {"project": Autocomplete(model=Project)}

    def clean(self):
        data = super().clean()
        if data.get("project") and data.get("project").closed_on:
            raise forms.ValidationError(
                {"project": _("This project is already closed.")}
            )
        return data


class ProjectAutocompleteForm(forms.Form):
    project = forms.ModelChoiceField(
        queryset=Project.objects.all(),
        widget=Autocomplete(model=Project),
        label=_("project"),
    )
