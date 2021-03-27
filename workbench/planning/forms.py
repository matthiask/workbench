import datetime as dt
from itertools import islice

from django import forms
from django.db.models import Sum
from django.utils.dateparse import parse_date
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.invoices.utils import recurring
from workbench.planning.models import PlannedWork
from workbench.projects.models import Project
from workbench.tools.formats import Z1, local_date_format
from workbench.tools.forms import Autocomplete, Form, ModelForm, Textarea, add_prefix
from workbench.tools.validation import monday


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

        if pk := request.GET.get("copy"):
            try:
                pw = PlannedWork.objects.get(pk=pk)
            except (PlannedWork.DoesNotExist, TypeError, ValueError):
                pass
            else:
                initial.update(
                    {
                        "project": pw.project_id,
                        "offer": pw.offer_id,
                        "title": pw.title,
                        "notes": pw.notes,
                        "planned_hours": pw.planned_hours,
                        "weeks": pw.weeks,
                    }
                )

        super().__init__(*args, **kwargs)
        self.instance.project = self.project

        self.fields[
            "offer"
        ].choices = self.instance.project.offers.not_declined_choices(
            include=self.instance.offer_id
        )

        date_from_options = [
            monday(),
            self.instance.weeks and min(self.instance.weeks),
            initial.get("weeks") and min(initial["weeks"]),
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

        """ XXX Check this after adding milestones
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
        """

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
