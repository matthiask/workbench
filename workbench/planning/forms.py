import datetime as dt
from itertools import islice

from django import forms
from django.db.models import Q
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.invoices.utils import recurring
from workbench.offers.models import Offer
from workbench.planning.models import PlannedWork, PlanningRequest
from workbench.projects.models import Project
from workbench.tools.formats import local_date_format
from workbench.tools.forms import Autocomplete, Form, ModelForm, Textarea, add_prefix
from workbench.tools.validation import monday, raise_if_errors


class PlanningRequestSearchForm(Form):
    project = forms.ModelChoiceField(
        queryset=Project.objects.all(),
        required=False,
        widget=Autocomplete(model=Project),
        label="",
    )
    created_by = forms.TypedChoiceField(
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["created_by"].choices = User.objects.choices(
            collapse_inactive=True, myself=True
        )

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("project"):
            queryset = queryset.filter(project=data.get("project"))
        queryset = self.apply_owned_by(queryset, attribute="created_by")
        return queryset.select_related(
            "created_by",
            "project__owned_by",
            "project__customer",
            "project__contact__organization",
        )


@add_prefix("modal")
class PlanningRequestForm(ModelForm):
    user_fields = default_to_current_user = ("created_by",)

    class Meta:
        model = PlanningRequest
        fields = (
            "project",
            "offer",
            "title",
            "description",
            "requested_hours",
            "earliest_start_on",
            "completion_requested_on",
            "receivers",
        )
        widgets = {
            "project": Autocomplete(model=Project, params={"only_open": "on"}),
            "offer": Autocomplete(model=Offer),
            "description": Textarea,
            "receivers": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        """
        self.project = kwargs.pop("project", None)
        if self.project:  # Creating a new offer
            kwargs.setdefault("initial", {}).update({"title": self.project.title})
        else:
            self.project = kwargs["instance"].project
        """

        super().__init__(*args, **kwargs)
        # self.instance.project = self.project

        q = Q(is_active=True)
        if self.instance.pk:
            q |= Q(id__in=self.instance.receivers.values_list("id", flat=True))
        self.fields["receivers"].queryset = User.objects.filter(q)

    def save(self):
        if self.instance.pk:
            return super().save()

        instance = super().save(commit=False)
        instance.created_by = self.request.user
        instance.save()
        self.save_m2m()
        return instance


class PlannedWorkSearchForm(Form):
    project = forms.ModelChoiceField(
        queryset=Project.objects.all(),
        required=False,
        widget=Autocomplete(model=Project),
        label="",
    )
    user = forms.TypedChoiceField(
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].choices = User.objects.choices(
            collapse_inactive=True, myself=True
        )

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("project"):
            queryset = queryset.filter(project=data.get("project"))
        queryset = self.apply_owned_by(queryset, attribute="user")
        return queryset.select_related(
            "user",
            "project__owned_by",
            "project__customer",
            "project__contact__organization",
        )


@add_prefix("modal")
class PlannedWorkForm(ModelForm):
    user_fields = default_to_current_user = ("user",)

    class Meta:
        model = PlannedWork
        fields = (
            "project",
            "offer",
            "request",
            "user",
            "title",
            "notes",
            "planned_hours",
        )
        widgets = {
            "project": Autocomplete(model=Project, params={"only_open": "on"}),
            "offer": Autocomplete(model=Offer),
            "notes": Textarea,
        }

    def __init__(self, *args, **kwargs):
        """
        self.project = kwargs.pop("project", None)
        if self.project:  # Creating a new offer
            kwargs.setdefault("initial", {}).update({"title": self.project.title})
        else:
            self.project = kwargs["instance"].project
        """

        initial = kwargs.setdefault("initial", {})
        request = kwargs["request"]
        for field in ["project", "offer", "request"]:
            if request.GET.get(field):
                initial.setdefault(field, request.GET.get(field))

        super().__init__(*args, **kwargs)
        # self.instance.project = self.project

        self.fields["project"].required = False

        self.fields["weeks"] = forms.MultipleChoiceField(
            label=capfirst(_("weeks")),
            choices=[
                (
                    day,
                    "KW{} ({} - {})".format(
                        local_date_format(day, fmt="W"),
                        local_date_format(day),
                        local_date_format(day + dt.timedelta(days=6)),
                    ),
                )
                for day in islice(recurring(monday(), "weekly"), 52)
            ],
            widget=forms.SelectMultiple(attrs={"size": 20}),
            initial=self.instance.weeks,
        )

    def clean(self):
        data = super().clean()
        errors = {}

        if not data.get("project") and data.get("offer"):
            data["project"] = data["offer"].project
        if not data.get("project") and data.get("request"):
            data["project"] = data["request"].project
        if not data.get("project"):
            errors["project"] = _("This field is required.")

        if data.get("offer") and data["offer"].project != data.get("project"):
            errors["offer"] = _("The offer must belong to the project above.")
        if data.get("request") and data["request"].project != data.get("project"):
            errors["request"] = _("The request must belong to the project above.")

        raise_if_errors(errors)
        return data

    def save(self):
        instance = super().save(commit=False)
        instance.weeks = self.cleaned_data.get("weeks")
        instance.save()
        return instance
