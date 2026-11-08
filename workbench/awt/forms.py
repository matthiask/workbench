import datetime as dt
from urllib.parse import urlencode

from django import forms
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from workbench.accounts.features import FEATURES
from workbench.accounts.models import Team, User
from workbench.awt.models import Absence, Year
from workbench.tools.forms import Form, ModelForm, Textarea, WarningsForm, add_prefix
from workbench.tools.validation import monday
from workbench.tools.xlsx import WorkbenchXLSXDocument


class AbsenceSearchForm(Form):
    u = forms.TypedChoiceField(
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )
    reason = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        choices=[("", _("All reasons")), *Absence.REASON_CHOICES],
        label="",
    )
    s = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        choices=[("", _("All states")), ("unconfirmed", _("Unconfirmed"))],
        label="",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["u"].choices = User.objects.choices(
            collapse_inactive=False, myself=True
        )

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("u") == -1:
            queryset = queryset.filter(user=self.request.user)
        elif data.get("u"):
            queryset = queryset.filter(user=data.get("u"))
        if data.get("reason"):
            queryset = queryset.filter(reason=data.get("reason"))
        if data.get("s") == "unconfirmed":
            queryset = queryset.unconfirmed()
        return queryset.select_related("user")

    def response(self, request, queryset):
        if (
            request.GET.get("export") == "xlsx"
            # The export contains the descriptions of sickness absences
            and request.user.features[FEATURES.PERSONNEL_ADMINISTRATION]
        ):
            xlsx = WorkbenchXLSXDocument()
            xlsx.table_from_queryset(queryset)
            return xlsx.to_response("absences.xlsx")
        return None


def employed(user, starts_on, ends_on):
    """Whether the user's employments cover all days from starts_on to
    ends_on; users without employments aren't in the annual working time"""
    if not user.employments.exists():
        return True
    day = starts_on
    for employment in user.employments.filter(
        date_from__lte=ends_on, date_until__gte=starts_on
    ).order_by("date_from"):
        if employment.date_from > day:
            return False
        # Open-ended employments end on dt.date.max, don't add to it
        if employment.date_until >= ends_on:
            return True
        day = max(day, employment.date_until + dt.timedelta(days=1))
    return False


@add_prefix("modal")
class AbsenceForm(ModelForm, WarningsForm):
    user_fields = default_to_current_user = ("user",)

    class Meta:
        model = Absence
        fields = ["user", "starts_on", "ends_on", "days", "reason", "description"]
        widgets = {"description": Textarea({"rows": 2})}

    def __init__(self, *args, **kwargs):
        initial = kwargs.setdefault("initial", {})
        request = kwargs["request"]
        for field in ["user", "starts_on", "ends_on", "days", "reason", "description"]:
            if value := request.GET.get(field):
                initial[field] = value

        super().__init__(*args, **kwargs)
        # A sickness absence with a description which is replaced, see clean()
        self.replaces = (
            Absence.objects.filter(pk=pk).first()
            if not self.instance.pk
            and (pk := request.GET.get("replaces", "")).isdigit()
            else None
        )
        self.fields["user"].choices = User.objects.choices(collapse_inactive=False)
        self.fields["days"].help_text = format_html(
            '<a href="#" data-hours-button="{hours}">{hours}</a>',
            hours=_("Enter hours"),
        )
        if not self.request.user.features[FEATURES.PERSONNEL_ADMINISTRATION]:
            # Absences can't be handed over to others, see Absence.allow_update
            if self.instance.pk:
                self.fields["user"].disabled = True
            self.fields["reason"].choices = [
                choice
                for choice in self.fields["reason"].choices
                if choice[0] != Absence.CORRECTION
            ]

    def clean(self):
        data = super().clean()
        if (days := data.get("days")) is not None and (
            days == 0 or (days < 0 and data.get("reason") != Absence.CORRECTION)
        ):
            self.add_error(
                "days",
                _("Absences need days, only corrections may be negative."),
            )
        if (starts_on := data.get("starts_on")) and (user := data.get("user")):
            today = dt.date.today()
            if not user.features[FEATURES.LATE_LOGGING] and starts_on.year < today.year:
                self.add_error(
                    "starts_on", _("Creating absences for past years is not allowed.")
                )

            elif starts_on.year < today.year:
                self.add_warning(
                    _(
                        "Creating absences for past years has effects on financial"
                        " statements, carry-forward entries etc. Are you sure?"
                    ),
                    code="past-years-absences",
                )

            elif (starts_on - today).days > 366:
                self.add_warning(
                    _(
                        "Impressive planning skills or wrong date?"
                        " Absence starts in more than one year."
                    ),
                    code="impressive-planning-skills",
                )

        if (
            (starts_on := data.get("starts_on"))
            and (user := data.get("user"))
            and data.get("reason") != Absence.CORRECTION
            and {"user", "starts_on", "ends_on"} & set(self.changed_data)
            and not employed(user, starts_on, data.get("ends_on") or starts_on)
        ):
            self.add_warning(
                _(
                    "%(user)s isn't employed during the whole absence. Absences"
                    " outside employments count as working time anyway."
                )
                % {"user": user},
                code="outside-employment",
            )

        # Only sickness descriptions are private. A new absence without the
        # description replaces the absence instead.
        if (
            self.instance.pk
            and self.instance.reason == Absence.SICKNESS
            and data.get("reason") not in {None, Absence.SICKNESS}
            and data.get("description")
        ):
            params = {
                "user": self.instance.user_id,
                "starts_on": data.get("starts_on"),
                "ends_on": data.get("ends_on"),
                "days": data.get("days"),
                "reason": data["reason"],
                "replaces": self.instance.pk,
            }
            self.add_error(
                "reason",
                format_html(
                    '{} <a href="{}?{}" data-ajaxmodal>{}</a>',
                    _(
                        "The description would become visible to everyone when"
                        " the reason isn't sickness anymore."
                    ),
                    Absence.urls["create"],
                    urlencode({
                        key: value for key, value in params.items() if value is not None
                    }),
                    _("Replace the absence with a new one without the description"),
                ),
            )

        if self.replaces and not Absence.allow_delete(self.replaces, self.request):
            raise forms.ValidationError(_("You cannot replace this absence."))

        return data

    def save(self, *args, **kwargs):
        self.instance.update_confirmation(
            self.request.user, changed_fields=self.changed_data
        )
        instance = super().save(*args, **kwargs)
        if self.replaces:
            self.replaces.delete()
        return instance


class CalendarFilterForm(Form):
    team = forms.ModelChoiceField(
        Team.objects.all(), empty_label=_("Everyone"), label="", required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["year"] = forms.ChoiceField(
            label="",
            required=False,
            choices=[("", _("Next 12 months"))]
            + [
                (str(year), str(year))
                for year in sorted(
                    Year.objects
                    .filter(year__lte=dt.date.today().year)
                    .order_by()
                    .values_list("year", flat=True)
                    .distinct(),
                    reverse=True,
                )
            ],
        )

    def users(self):
        data = self.cleaned_data
        queryset = User.objects.active()
        if data.get("team"):
            queryset = queryset.filter(teams=data.get("team"))
        return queryset

    def cutoff(self):
        year = self.cleaned_data["year"]
        if not year:
            return monday() - dt.timedelta(days=7)
        return monday(dt.date(int(year), 1, 1))
