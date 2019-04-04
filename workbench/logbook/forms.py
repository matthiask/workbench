from datetime import date, timedelta
from decimal import ROUND_UP, Decimal

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.contacts.models import Organization
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.projects.models import Project, Service
from workbench.tools.forms import ModelForm, Picker, Textarea
from workbench.tools.validation import raise_if_errors
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rendered_by"].choices = User.objects.choices(
            collapse_inactive=False
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

    def response(self, request, queryset):
        if request.GET.get("xlsx"):
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

    def response(self, request, queryset):
        if request.GET.get("xlsx"):
            xlsx = WorkbenchXLSXDocument()
            xlsx.logged_costs(queryset)
            return xlsx.to_response("costs.xlsx")


class LoggedHoursForm(ModelForm):
    user_fields = default_to_current_user = ("rendered_by",)

    service_title = forms.CharField(label=_("title"), required=False, max_length=200)
    service_description = forms.CharField(
        label=_("description"), required=False, widget=Textarea({"rows": 2})
    )

    class Meta:
        model = LoggedHours
        fields = ("rendered_by", "rendered_on", "service", "hours", "description")
        widgets = {"description": Textarea({"rows": 2})}

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
            if timesince and timesince < 4 * 3600:
                initial.setdefault(
                    "hours",
                    (timesince / Decimal(3600)).quantize(
                        Decimal("0.0"), rounding=ROUND_UP
                    ),
                )

            if request.GET.get("service"):
                initial["service"] = request.GET.get("service")

            else:
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
        self.fields["service"].choices = self.project.services.logging().choices()
        self.fields["service"].required = False
        if len(self.fields["service"].choices) > 1 and not self.request.POST.get(
            "service_title"
        ):
            self.hide_new_service = True
            self.fields["service"].widget.attrs["autofocus"] = True
        else:
            self.fields["service_title"].widget.attrs["autofocus"] = True

        if self.instance.pk:
            self.fields.pop("service_title")
            self.fields.pop("service_description")
            today = date.today()
            if self.instance.rendered_on < date.today() - timedelta(
                days=today.weekday()
            ):
                self.fields["hours"].disabled = True
                self.fields["rendered_by"].disabled = True
                self.fields["rendered_on"].disabled = True

    def clean(self):
        data = super().clean()
        errors = {}
        if not data["service"] and not data["service_title"]:
            errors["service"] = _(
                "This field is required unless you create a new service."
            )
        if self.project.closed_on:
            self.add_warning(_("This project is already closed."))
        if self.instance.invoice_service:
            self.add_warning(_("This entry is already part of an invoice."))

        if all((not self.instance.pk, data["rendered_by"], data["rendered_on"])):
            today = date.today()
            if not data["rendered_by"].enforce_same_week_logging:
                # Fine
                pass
            elif data["rendered_on"] < date.today() - timedelta(days=today.weekday()):
                errors["rendered_on"] = _(
                    "Sorry, hours have to be logged in the same week."
                )
            elif data["rendered_on"] > date.today() + timedelta(days=7):
                errors["rendered_on"] = _("Sorry, too early.")

        try:
            latest = LoggedHours.objects.filter(rendered_by=self.request.user).latest(
                "pk"
            )
        except LoggedHours.DoesNotExist:
            pass
        else:
            fields = ["rendered_by", "rendered_on", "service", "hours", "description"]
            for field in fields:
                if data[field] != getattr(latest, field):
                    break
            else:
                self.add_warning(_("This seems to be a duplicate. Is it?"))

        raise_if_errors(errors)
        return data

    def save(self):
        instance = super().save(commit=False)
        if not instance.pk:
            instance.created_by = self.request.user
        if not self.cleaned_data.get("service") and self.cleaned_data.get(
            "service_title"
        ):
            instance.service = Service.objects.create(
                project=self.project,
                title=self.cleaned_data["service_title"],
                description=self.cleaned_data["service_description"],
            )
        instance.save()
        return instance


class LoggedCostForm(ModelForm):
    class Meta:
        model = LoggedCost
        fields = ("service", "rendered_on", "third_party_costs", "cost", "description")
        widgets = {"description": Textarea({"rows": 2})}

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project", None)
        if self.project:
            kwargs.setdefault("initial", {}).setdefault(
                "service", kwargs["request"].GET.get("service")
            )
        else:
            self.project = kwargs["instance"].project

        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.instance.created_by = self.request.user
            self.instance.project = self.project

        self.fields["service"].choices = self.project.services.logging().choices()
        # TODO add JS for those buttons
        # self.fields["third_party_costs"].help_text = mark_safe(
        #     "{}"
        #     ' <button type="button" class="btn btn-secondary btn-sm">1:1</button>'
        #     ' <button type="button" class="btn btn-secondary btn-sm">+15%</button>'
        #     "".format(self.fields["third_party_costs"].help_text)
        # )

    def clean(self):
        data = super().clean()
        if self.project.closed_on:
            self.add_warning(_("This project is already closed."))
        if self.instance.invoice_service:
            self.add_warning(_("This entry is already part of an invoice."))
        return data
