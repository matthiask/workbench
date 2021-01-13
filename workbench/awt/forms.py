import datetime as dt

from django import forms
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.awt.models import Absence
from workbench.tools.forms import Form, ModelForm, Textarea, WarningsForm, add_prefix
from workbench.tools.xlsx import WorkbenchXLSXDocument


class AbsenceSearchForm(Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Search")}
        ),
        label="",
    )
    u = forms.TypedChoiceField(
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )
    reason = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
        choices=[("", _("All reasons"))] + Absence.REASON_CHOICES,
        label="",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["u"].choices = User.objects.choices(
            collapse_inactive=False, myself=True
        )

    def filter(self, queryset):
        data = self.cleaned_data
        queryset = queryset.search(data.get("q"))
        if data.get("u") == -1:
            queryset = queryset.filter(user=self.request.user)
        elif data.get("u"):
            queryset = queryset.filter(user=data.get("u"))
        if data.get("reason"):
            queryset = queryset.filter(reason=data.get("reason"))
        return queryset.select_related("user")

    def response(self, request, queryset):
        if (
            request.GET.get("export") == "xlsx"
            and request.user.features[FEATURES.CONTROLLING]
        ):
            xlsx = WorkbenchXLSXDocument()
            xlsx.table_from_queryset(queryset)
            return xlsx.to_response("absences.xlsx")


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
        self.fields["days"].help_text = format_html(
            '<a href="#" data-hours-button="{hours}">{hours}</a>',
            hours=_("Enter hours"),
        )
        if not self.request.user.features[FEATURES.WORKING_TIME_CORRECTION]:
            self.fields["reason"].choices = [
                choice
                for choice in self.fields["reason"].choices
                if choice[0] != Absence.CORRECTION
            ]

    def clean(self):
        data = super().clean()
        if (starts_on := data.get("starts_on")) and (user := data.get("user")):
            today = dt.date.today()
            if user.enforce_same_week_logging and starts_on.year < today.year:
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

        return data
