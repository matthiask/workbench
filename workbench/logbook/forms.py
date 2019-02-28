from decimal import Decimal, ROUND_UP

from django import forms
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone

from workbench.accounts.models import User
from workbench.logbook.models import LoggedHours, LoggedCost
from workbench.tools.forms import ModelForm, Textarea


class LoggedHoursSearchForm(forms.Form):
    rendered_by = forms.ModelChoiceField(
        queryset=User.objects.all(),
        label=_("rendered by"),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label=_("All users"),
    )

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("rendered_by"):
            queryset = queryset.filter(rendered_by=data.get("rendered_by"))

        return queryset


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
                initial.setdefault("service", latest_on_project.service_id)
        else:
            self.project = kwargs["instance"].service.project

        super().__init__(*args, **kwargs)
        self.fields["service"].choices = [("", "----------")] + [
            (service.id, service.__str__()) for service in self.project.services.all()
        ]
        self.fields["service"].widget.attrs["autofocus"] = True

    def save(self):
        instance = super().save(commit=False)
        if not instance.pk:
            instance.created_by = self.request.user
        instance.save()
        return instance


class LoggedCostForm(ModelForm):
    class Meta:
        model = LoggedCost
        fields = ("service", "rendered_on", "cost", "description")
        widgets = {"description": Textarea()}

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project", None)
        if self.project:
            initial = kwargs.setdefault("initial", {})
            request = kwargs["request"]

            if request.GET.get("service"):
                initial["service"] = request.GET.get("service")

        else:
            self.project = self.instance.project

        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = self.fields["service"].queryset.filter(
            project=self.project
        )

    def save(self):
        instance = super().save(commit=False)
        if not instance.pk:
            instance.project = self.project
            instance.created_by = self.request.user
        instance.save()
        return instance
