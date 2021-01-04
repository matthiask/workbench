import datetime as dt
from itertools import islice

from django import forms
from django.db.models import Q, Sum
from django.utils.dateparse import parse_date
from django.utils.html import format_html, format_html_join
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import Team, User
from workbench.invoices.utils import recurring
from workbench.planning.models import PlannedWork, PlanningRequest
from workbench.projects.models import Project
from workbench.tools.formats import Z1, local_date_format
from workbench.tools.forms import Autocomplete, Form, ModelForm, Textarea, add_prefix
from workbench.tools.validation import monday


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
            "offer",
            "title",
            "description",
            "is_provisional",
            "requested_hours",
            "earliest_start_on",
            "completion_requested_on",
            "receivers",
        )
        widgets = {
            "description": Textarea,
            "receivers": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project", None)
        if self.project:  # Creating a new object
            kwargs.setdefault("initial", {}).update({"title": self.project.title})
        else:
            self.project = kwargs["instance"].project

        initial = kwargs.setdefault("initial", {})
        request = kwargs["request"]

        if offer_id := request.GET.get("plan_offer"):
            try:
                offer = self.project.offers.get(pk=offer_id)
            except (self.project.offers.model.DoesNotExist, TypeError, ValueError):
                pass
            else:
                initial.update(
                    {
                        "title": offer.title,
                        "description": offer.description,
                        "requested_hours": offer.services.aggregate(
                            h=Sum("service_hours")
                        )["h"]
                        or Z1,
                    }
                )

        if service_id := request.GET.get("service"):
            try:
                service = self.project.services.get(pk=service_id)
            except (self.project.services.model.DoesNotExist, TypeError, ValueError):
                pass
            else:
                initial.update(
                    {
                        "title": f"{self.project.title}: {service.title}",
                        "description": service.description,
                        "requested_hours": service.service_hours,
                    }
                )

        super().__init__(*args, **kwargs)
        self.instance.project = self.project

        self.fields[
            "offer"
        ].choices = self.instance.project.offers.not_declined_choices(
            include=self.instance.offer_id
        )

        q = Q(is_active=True)
        if self.instance.pk:
            q |= Q(id__in=self.instance.receivers.values_list("id", flat=True))
        self.fields["receivers"].queryset = User.objects.filter(q)
        self.fields["receivers"].help_text = format_html(
            "{}: {}",
            _("Select team"),
            format_html_join(
                ", ",
                '<a href="#" data-select-receivers="{}">{}</a>',
                [
                    (",".join(str(member.id) for member in team.members.all()), team)
                    for team in Team.objects.prefetch_related("members")
                ],
            ),
        )

    def clean(self):
        data = super().clean()

        if data.get("offer") and data["offer"].is_declined:
            self.add_warning(
                _("The selected offer is declined."), code="offer-is-declined"
            )

        return data

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
            "offer",
            "request",
            "user",
            "title",
            "notes",
            "planned_hours",
        )
        widgets = {
            "notes": Textarea,
        }

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project", None)
        if not self.project:  # Updating
            self.project = kwargs["instance"].project

        initial = kwargs.setdefault("initial", {})
        request = kwargs["request"]
        for field in ["offer"]:
            if value := request.GET.get(field):
                initial.setdefault(field, value)

        pr = None
        if pr_id := request.POST.get("request") or request.GET.get("request"):
            try:
                pr = self.project.planning_requests.get(pk=pr_id)
            except (PlanningRequest.DoesNotExist, TypeError, ValueError):
                pass
            else:
                initial.setdefault("offer", pr.offer_id)
                initial.update(
                    {
                        "request": pr.id,
                        "title": pr.title,
                        "planned_hours": pr.requested_hours - pr.planned_hours,
                        "weeks": pr.weeks,
                    }
                )

        if offer_id := request.GET.get("plan_offer"):
            try:
                offer = self.project.offers.get(pk=offer_id)
            except (self.project.offers.model.DoesNotExist, TypeError, ValueError):
                pass
            else:
                initial.update(
                    {
                        "title": offer.title,
                        "notes": offer.description,
                        "planned_hours": offer.services.aggregate(
                            h=Sum("service_hours")
                        )["h"]
                        or Z1,
                    }
                )

        if service_id := request.GET.get("service"):
            try:
                service = self.project.services.get(pk=service_id)
            except (self.project.services.model.DoesNotExist, TypeError, ValueError):
                pass
            else:
                initial.update(
                    {
                        "title": f"{self.project.title}: {service.title}",
                        "notes": service.description,
                        "planned_hours": service.service_hours,
                    }
                )

        super().__init__(*args, **kwargs)
        self.instance.project = self.project

        self.fields[
            "offer"
        ].choices = self.instance.project.offers.not_declined_choices(
            include=self.instance.offer_id
        )
        self.fields["request"].queryset = self.instance.project.planning_requests.all()

        date_from_options = [
            monday(),
            self.instance.weeks and min(self.instance.weeks),
            pr and min(pr.weeks),
        ]
        date_from = min(filter(None, date_from_options)) - dt.timedelta(days=21)

        self.fields["weeks"] = forms.TypedMultipleChoiceField(
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
                for day in islice(recurring(date_from, "weekly"), 80)
            ],
            widget=forms.SelectMultiple(attrs={"size": 20}),
            initial=self.instance.weeks or [monday()],
            coerce=parse_date,
        )

    def clean(self):
        data = super().clean()

        if data.get("request") and data.get("weeks"):
            outside = [
                week
                for week in data["weeks"]
                if week < data["request"].earliest_start_on
                or week >= data["request"].completion_requested_on
            ]
            if outside:
                self.add_warning(
                    _(
                        "At least one week is outside the requested range of"
                        " %(from)s – %(until)s: %(weeks)s"
                    )
                    % {
                        "from": local_date_format(data["request"].earliest_start_on),
                        "until": local_date_format(
                            data["request"].completion_requested_on
                            - dt.timedelta(days=1)
                        ),
                        "weeks": ", ".join(local_date_format(week) for week in outside),
                    },
                    code="weeks-outside-request",
                )

        if data.get("offer") and data["offer"].is_declined:
            self.add_warning(
                _("The selected offer is declined."), code="offer-is-declined"
            )

        return data

    def save(self):
        instance = super().save(commit=False)
        instance.weeks = self.cleaned_data.get("weeks")
        instance.save()
        return instance
