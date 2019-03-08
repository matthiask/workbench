from datetime import date, timedelta
from decimal import Decimal, ROUND_UP

from django import forms
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone

from workbench.accounts.models import User
from workbench.contacts.models import Organization
from workbench.logbook.models import LoggedHours, LoggedCost
from workbench.projects.models import Project, Service
from workbench.tools.forms import ModelForm, Picker, Textarea
from workbench.tools.xlsx import WorkbenchXLSXDocument


class LoggedHoursSearchForm(forms.Form):
    rendered_by = forms.ModelChoiceField(
        queryset=User.objects.all(),
        label=_("rendered by"),
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
        empty_label=_("All users"),
    )
    project = forms.ModelChoiceField(
        queryset=Project.objects.all(),
        label=_("project"),
        required=False,
        widget=Picker(model=Project),
    )
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        label=_("organization"),
        required=False,
        widget=Picker(model=Organization),
    )
    service = forms.ModelChoiceField(
        queryset=Service.objects.all(), required=False, widget=forms.HiddenInput
    )

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("rendered_by"):
            queryset = queryset.filter(rendered_by=data.get("rendered_by"))
        if data.get("project"):
            queryset = queryset.filter(service__project=data.get("project"))
        if data.get("organization"):
            queryset = queryset.filter(
                service__project__customer=data.get("organization")
            )

        # "hidden" filters
        if data.get("service"):
            queryset = queryset.filter(service=data.get("service"))

        return queryset.select_related("service__project__owned_by", "rendered_by")

    def response(self, response, queryset):
        if response.GET.get("xlsx"):
            xlsx = WorkbenchXLSXDocument()
            xlsx.logged_hours(queryset)
            return xlsx.to_response("hours.xlsx")


class LoggedCostSearchForm(forms.Form):
    created_by = forms.ModelChoiceField(
        queryset=User.objects.all(),
        label=_("created by"),
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
        empty_label=_("All users"),
    )
    project = forms.ModelChoiceField(
        queryset=Project.objects.all(),
        label=_("project"),
        required=False,
        widget=Picker(model=Project),
    )
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        label=_("organization"),
        required=False,
        widget=Picker(model=Organization),
    )
    service = forms.IntegerField(
        label=_("service"), required=False, widget=forms.HiddenInput
    )

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("created_by"):
            queryset = queryset.filter(created_by=data.get("created_by"))
        if data.get("project"):
            queryset = queryset.filter(project=data.get("project"))
        if data.get("organization"):
            queryset = queryset.filter(project__customer=data.get("organization"))

        # "hidden" filters
        if data.get("service") == 0:
            queryset = queryset.filter(service=None)
        elif data.get("service"):
            queryset = queryset.filter(service=data.get("service"))

        return queryset.select_related("project__owned_by", "service", "created_by")

    def response(self, response, queryset):
        if response.GET.get("xlsx"):
            xlsx = WorkbenchXLSXDocument()
            xlsx.logged_costs(queryset)
            return xlsx.to_response("costs.xlsx")


class LoggedHoursForm(ModelForm):
    user_fields = default_to_current_user = ("rendered_by",)

    class Meta:
        model = LoggedHours
        fields = ("rendered_by", "rendered_on", "service", "hours", "description")
        widgets = {"description": Textarea()}

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project", None)
        if self.project:
            initial = kwargs.setdefault("initial", {})
            request = kwargs["request"]

            latest = (
                LoggedHours.objects.filter(rendered_by=request.user)
                .order_by("-created_at")
                .first()
            )
            timesince = latest and int(
                (timezone.now() - latest.created_at).total_seconds()
            )
            if timesince and timesince < 3 * 3600:
                initial.setdefault(
                    "hours",
                    (timesince / Decimal(3600)).quantize(
                        Decimal("0.0"), rounding=ROUND_UP
                    ),
                )

            if request.GET.get("service"):
                initial["service"] = request.GET.get("service")

            elif "service" not in initial:
                latest_on_project = (
                    LoggedHours.objects.filter(
                        rendered_by=request.user, service__project=self.project
                    )
                    .order_by("-created_at")
                    .first()
                )
                if latest_on_project:
                    initial.setdefault("service", latest_on_project.service_id)
        else:
            self.project = kwargs["instance"].service.project

        super().__init__(*args, **kwargs)
        self.fields["service"].choices = self.project.services.choices()
        self.fields["service"].widget.attrs["autofocus"] = True

        today = date.today()
        if self.instance.pk and self.instance.rendered_on < date.today() - timedelta(
            days=today.weekday()
        ):
            self.fields["hours"].disabled = True
            self.fields["rendered_by"].disabled = True
            self.fields["rendered_on"].disabled = True

    def clean_rendered_on(self):
        rendered_on = self.cleaned_data.get("rendered_on")
        if rendered_on:
            today = date.today()
            if not self.instance.pk and self.cleaned_data[
                "rendered_on"
            ] < date.today() - timedelta(days=today.weekday()):
                raise forms.ValidationError(
                    _("Sorry, hours have to be logged in the same week.")
                )
        return rendered_on

    def save(self):
        instance = super().save(commit=False)
        if not instance.pk:
            instance.created_by = self.request.user
        instance.save()
        return instance


class LoggedCostForm(ModelForm):
    class Meta:
        model = LoggedCost
        fields = ("service", "rendered_on", "cost", "third_party_costs", "description")
        widgets = {"description": Textarea()}

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project", None)
        if self.project:
            initial = kwargs.setdefault("initial", {})
            request = kwargs["request"]

            if request.GET.get("service"):
                initial["service"] = request.GET.get("service")

        else:
            self.project = kwargs["instance"].project

        super().__init__(*args, **kwargs)
        self.fields["service"].choices = self.project.services.choices()

    def save(self):
        instance = super().save(commit=False)
        if not instance.pk:
            instance.project = self.project
            instance.created_by = self.request.user
        instance.save()
        return instance
