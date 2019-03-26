from datetime import date

from django import forms
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.contacts.models import Organization, Person
from workbench.projects.models import Project, Service
from workbench.services.models import ServiceType
from workbench.tools.forms import ModelForm, Picker, Textarea


class ProjectSearchForm(forms.Form):
    s = forms.ChoiceField(
        choices=(("all", _("All states")), ("", _("Open")), ("closed", _("Closed"))),
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
    )
    org = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        required=False,
        widget=Picker(model=Organization),
    )
    type = forms.ChoiceField(
        choices=[("", _("All types"))] + Project.TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
    )
    owned_by = forms.TypedChoiceField(
        label=_("owned by"),
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
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
            "customer": Picker(model=Organization),
            "contact": Picker(model=Person),
            "description": Textarea,
            "type": forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        initial = kwargs.setdefault("initial", {})
        request = kwargs["request"]

        if request.GET.get("copy_project"):
            try:
                project = Project.objects.get(pk=request.GET["copy_project"])
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
                    }
                )
                if project.owned_by.is_active:
                    initial["owned_by"] = project.owned_by_id

        super().__init__(*args, **kwargs)
        self.fields["type"].choices = Project.TYPE_CHOICES
        if self.instance.pk:
            self.fields["is_closed"] = forms.BooleanField(
                label=_("is closed"),
                required=False,
                initial=bool(self.instance.closed_on),
            )

    def save(self):
        instance = super().save(commit=False)
        if not instance.closed_on and self.cleaned_data.get("is_closed"):
            instance.closed_on = date.today()
        if instance.closed_on and not self.cleaned_data.get("is_closed"):
            instance.closed_on = None
        instance.save()
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
            "offer",
            "title",
            "description",
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

        kwargs.setdefault("initial", {}).setdefault(
            "offer", kwargs["request"].GET.get("offer")
        )

        super().__init__(*args, **kwargs)

        self.fields["offer"].queryset = self.project.offers.all()
        self.instance.project = self.project


class DeleteServiceForm(ModelForm):
    class Meta:
        model = Service
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.loggedhours.exists() or self.instance.loggedcosts.exists():
            self.fields["merge_into"] = forms.ModelChoiceField(
                queryset=self.instance.project.services.exclude(pk=self.instance.pk),
                label=_("Merge log into"),
            )

    def save(self):
        if "merge_into" in self.cleaned_data:
            into = self.cleaned_data["merge_into"]
            self.instance.loggedhours.update(service=into)
            self.instance.loggedcosts.update(service=into)
        self.instance.delete()
        return into
