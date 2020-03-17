from decimal import ROUND_UP, Decimal

from django import forms
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from django.utils.html import mark_safe
from django.utils.translation import gettext, gettext_lazy as _, override

from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.contacts.models import Organization
from workbench.expenses.models import ExchangeRates
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.projects.models import Project, Service
from workbench.tools.forms import (
    Autocomplete,
    DateInput,
    Form,
    ModelForm,
    Textarea,
    add_prefix,
)
from workbench.tools.validation import in_days, logbook_lock, raise_if_errors
from workbench.tools.xlsx import WorkbenchXLSXDocument


class LoggedHoursSearchForm(Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Search")}
        ),
        label="",
    )
    rendered_by = forms.TypedChoiceField(
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )
    project = forms.ModelChoiceField(
        queryset=Project.objects.all(),
        required=False,
        widget=Autocomplete(model=Project),
        label="",
    )
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        required=False,
        widget=Autocomplete(model=Organization),
        label="",
    )
    date_from = forms.DateField(widget=DateInput, required=False, label="")
    date_until = forms.DateField(
        widget=DateInput, required=False, label=mark_safe("&ndash;&nbsp;")
    )
    service = forms.ModelChoiceField(
        queryset=Service.objects.all(),
        required=False,
        widget=forms.HiddenInput,
        label="",
    )
    circle = forms.IntegerField(required=False, widget=forms.HiddenInput, label="",)
    role = forms.IntegerField(required=False, widget=forms.HiddenInput, label="",)
    not_archived = forms.BooleanField(
        required=False, widget=forms.HiddenInput, label=""
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rendered_by"].choices = User.objects.choices(
            collapse_inactive=False, myself=True
        )

    def filter(self, queryset):
        data = self.cleaned_data
        queryset = queryset.search(data.get("q"))
        if data.get("rendered_by") == -1:
            queryset = queryset.filter(rendered_by=self.request.user)
        elif data.get("rendered_by"):
            queryset = queryset.filter(rendered_by=data.get("rendered_by"))
        if data.get("project"):
            queryset = queryset.filter(service__project=data.get("project"))
        if data.get("organization"):
            queryset = queryset.filter(
                service__project__customer=data.get("organization")
            )
        if data.get("date_from"):
            queryset = queryset.filter(rendered_on__gte=data.get("date_from"))
        if data.get("date_until"):
            queryset = queryset.filter(rendered_on__lte=data.get("date_until"))

        # "hidden" filters
        if data.get("service"):
            queryset = queryset.filter(service=data.get("service"))
        if data.get("circle") == 0:
            queryset = queryset.filter(service__role__isnull=True)
        elif data.get("circle"):
            queryset = queryset.filter(service__role__circle=data.get("circle"))
        if data.get("role"):
            queryset = queryset.filter(service__role=data.get("role"))
        if data.get("not_archived"):
            queryset = queryset.filter(archived_at__isnull=True)

        return queryset.select_related("service__project__owned_by", "rendered_by")

    def response(self, request, queryset):
        if request.GET.get("xlsx") and request.user.features[FEATURES.CONTROLLING]:
            xlsx = WorkbenchXLSXDocument()
            xlsx.logged_hours(queryset)
            return xlsx.to_response("hours.xlsx")


class LoggedCostSearchForm(Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Search")}
        ),
        label="",
    )
    rendered_by = forms.TypedChoiceField(
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )
    project = forms.ModelChoiceField(
        queryset=Project.objects.all(),
        required=False,
        widget=Autocomplete(model=Project),
        label="",
    )
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        required=False,
        widget=Autocomplete(model=Organization),
        label="",
    )
    expenses = forms.BooleanField(required=False, label=_("expenses"))
    date_from = forms.DateField(widget=DateInput, required=False, label="")
    date_until = forms.DateField(
        widget=DateInput, required=False, label=mark_safe("&ndash;&nbsp;")
    )
    service = forms.IntegerField(required=False, widget=forms.HiddenInput, label="")
    not_archived = forms.BooleanField(
        required=False, widget=forms.HiddenInput, label=""
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rendered_by"].choices = User.objects.choices(
            collapse_inactive=False, myself=True
        )

    def filter(self, queryset):
        data = self.cleaned_data
        queryset = queryset.search(data.get("q"))
        if data.get("rendered_by") == -1:
            queryset = queryset.filter(rendered_by=self.request.user)
        elif data.get("rendered_by"):
            queryset = queryset.filter(rendered_by=data.get("rendered_by"))
        if data.get("project"):
            queryset = queryset.filter(service__project=data.get("project"))
        if data.get("organization"):
            queryset = queryset.filter(
                service__project__customer=data.get("organization")
            )
        if data.get("expenses"):
            queryset = queryset.filter(are_expenses=True)
        if data.get("date_from"):
            queryset = queryset.filter(rendered_on__gte=data.get("date_from"))
        if data.get("date_until"):
            queryset = queryset.filter(rendered_on__lte=data.get("date_until"))

        # "hidden" filters
        if data.get("service") == 0:
            queryset = queryset.filter(service=None)
        elif data.get("service"):
            queryset = queryset.filter(service=data.get("service"))
        if data.get("not_archived"):
            queryset = queryset.filter(archived_at__isnull=True)

        return queryset.select_related("service__project__owned_by", "rendered_by")

    def response(self, request, queryset):
        if request.GET.get("xlsx") and request.user.features[FEATURES.CONTROLLING]:
            xlsx = WorkbenchXLSXDocument()
            xlsx.logged_costs(queryset)
            return xlsx.to_response("costs.xlsx")


@add_prefix("modal")
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

            if request.GET.get("copy"):
                try:
                    hours = LoggedHours.objects.get(pk=request.GET["copy"])
                except (LoggedHours.DoesNotExist, TypeError, ValueError):
                    pass
                else:
                    initial.update(
                        {
                            "service": hours.service_id,
                            "rendered_on": hours.rendered_on.isoformat(),
                            "hours": hours.hours,
                            "description": hours.description,
                        }
                    )

            if request.GET.get("hours"):
                initial["hours"] = request.GET["hours"]

            elif not initial.get("hours"):
                timesince = request.user.latest_created_at and int(
                    (timezone.now() - request.user.latest_created_at).total_seconds()
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

            elif not initial.get("service"):
                latest_on_project = (
                    LoggedHours.objects.filter(
                        rendered_by=request.user, service__project=self.project
                    )
                    .order_by("-created_at")
                    .first()
                )
                if latest_on_project:
                    initial.setdefault("service", latest_on_project.service_id)

            for field in ["rendered_on", "description"]:
                if request.GET.get(field):
                    initial[field] = request.GET.get(field)

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
            if (
                self.instance.rendered_by.enforce_same_week_logging
                and self.instance.rendered_on < logbook_lock()
            ):
                self.fields["hours"].disabled = True
                self.fields["rendered_by"].disabled = True
                self.fields["rendered_on"].disabled = True

    def clean(self):
        data = super().clean()
        errors = {}
        if not data["service"] and not data.get("service_title"):
            errors["service"] = _(
                "This field is required unless you create a new service."
            )
        elif data["service"] and data.get("service_title"):
            errors["service"] = _(
                "Deselect the existing service if you want to create a new service."
            )
        if self.project.closed_on:
            if self.project.closed_on < in_days(-14):
                errors["__all__"] = _("This project has been closed too long ago.")
            else:
                self.add_warning(
                    _("This project has been closed recently."), code="project-closed"
                )
        if self.instance.invoice_service:
            self.add_warning(
                _("This entry is already part of an invoice."), code="part-of-invoice"
            )

        if all(
            f in self.fields and data.get(f) for f in ["rendered_by", "rendered_on"]
        ) and (not self.instance.pk or ("rendered_on" in self.changed_data)):
            if not data["rendered_by"].enforce_same_week_logging:
                # Fine
                pass
            elif data["rendered_on"] < logbook_lock():
                errors["rendered_on"] = _(
                    "Sorry, hours have to be logged in the same week."
                )
            elif data["rendered_on"] > in_days(7):
                errors["rendered_on"] = _("Sorry, that's too far in the future.")

        try:
            latest = LoggedHours.objects.filter(
                Q(rendered_by=self.request.user), ~Q(id=self.instance.id)
            ).latest("pk")
        except LoggedHours.DoesNotExist:
            pass
        else:
            fields = ["rendered_by", "rendered_on", "service", "hours", "description"]
            for field in fields:
                if data.get(field) != getattr(latest, field):
                    break
            else:
                self.add_warning(
                    _("This seems to be a duplicate. Is it?"), code="maybe-duplicate"
                )

        raise_if_errors(errors)
        return data

    def save(self):
        instance = super().save(commit=False)
        if not instance.pk:
            instance.created_by = self.request.user
        if not self.cleaned_data.get("service") and self.cleaned_data.get(
            "service_title"
        ):
            service = Service(
                project=self.project,
                title=self.cleaned_data["service_title"],
                description=self.cleaned_data["service_description"],
            )
            if self.project.flat_rate is not None:
                with override(settings.WORKBENCH.PDF_LANGUAGE):
                    service.effort_type = gettext("flat rate")
                    service.effort_rate = self.project.flat_rate
            service.save()
            instance.service = service
        instance.save()
        return instance


@add_prefix("modal")
class LoggedCostForm(ModelForm):
    user_fields = default_to_current_user = ("rendered_by",)

    class Meta:
        model = LoggedCost
        fields = (
            "service",
            "rendered_by",
            "rendered_on",
            "expense_currency",
            "expense_cost",
            "third_party_costs",
            "are_expenses",
            "cost",
            "description",
        )
        widgets = {"description": Textarea({"rows": 2})}

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project", None)
        if self.project:
            kwargs.setdefault("initial", {}).setdefault(
                "service", kwargs["request"].GET.get("service")
            )
        else:
            self.project = kwargs["instance"].service.project

        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.instance.created_by = self.request.user

        self.fields["service"].choices = self.project.services.logging().choices()
        self.fields["cost"].help_text = mark_safe(
            "{} "
            '<a href="#" data-multiply-cost="1" class="">100%</a> '
            '<a href="#" data-multiply-cost="1.15" class="">115%</a> '
            "{}"
            "".format(
                _("Copy value from third party costs"), self.fields["cost"].help_text
            )
        )

        if self.instance.expense_report:
            self.fields["rendered_by"].disabled = True
            self.fields["rendered_on"].disabled = True
            self.fields["are_expenses"].disabled = True
            self.fields["third_party_costs"].disabled = True
            self.fields["expense_currency"].disabled = True
            self.fields["expense_cost"].disabled = True

        if self.request.user.features[FEATURES.FOREIGN_CURRENCIES]:
            rates = ExchangeRates.objects.newest()
            self.fields["expense_currency"] = forms.ChoiceField(
                choices=[("", "----------")]
                + [(currency, currency) for currency in rates.rates["rates"]],
                widget=forms.Select(attrs={"class": "custom-select"}),
                required=False,
                initial=self.instance.expense_currency,
                label=self.instance._meta.get_field("expense_currency").verbose_name,
            )
        else:
            self.fields.pop("expense_currency")
            self.fields.pop("expense_cost")

    def clean(self):
        data = super().clean()
        errors = {}
        if self.project.closed_on:
            if self.project.closed_on < in_days(-14):
                errors["__all__"] = _("This project has been closed too long ago.")
            else:
                self.add_warning(
                    _("This project has been closed recently."), code="project-closed"
                )
        if self.instance.invoice_service:
            self.add_warning(
                _("This entry is already part of an invoice."), code="part-of-invoice"
            )
        if data.get("are_expenses") and not data.get("third_party_costs"):
            errors["third_party_costs"] = (
                _("Providing third party costs is necessary for expenses."),
            )
        if data.get("cost") and data.get("third_party_costs") is not None:
            if data["cost"] < data["third_party_costs"]:
                self.add_warning(
                    _("Third party costs shouldn't be higher than costs."),
                    code="third-party-costs-higher",
                )
        if data.get("rendered_on") and data["rendered_on"] > in_days(7):
            errors["rendered_on"] = _("Sorry, that's too far in the future.")
        raise_if_errors(errors)
        return data
