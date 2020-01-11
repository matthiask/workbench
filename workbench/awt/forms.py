import datetime as dt

from django import forms
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.awt.models import Absence
from workbench.tools.forms import Form, ModelForm, Textarea, add_prefix


class AbsenceSearchForm(Form):
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
        # queryset = queryset.search(data.get("q"))
        if data.get("u") == -1:
            queryset = queryset.filter(user=self.request.user)
        elif data.get("u"):
            queryset = queryset.filter(user=data.get("u"))
        if data.get("reason"):
            queryset = queryset.filter(reason=data.get("reason"))
        return queryset.select_related("user")


@add_prefix("modal")
class AbsenceForm(ModelForm):
    user_fields = default_to_current_user = ("user",)

    class Meta:
        model = Absence
        fields = ["user", "starts_on", "ends_on", "days", "description", "reason"]
        widgets = {"description": Textarea({"rows": 2}), "reason": forms.RadioSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["days"].help_text = format_html(
            '<a href="#" data-hours-button="{hours}">{hours}</a>',
            hours=_("Enter hours"),
        )
        self.fields["reason"].choices = Absence.REASON_CHOICES

    def clean(self):
        data = super().clean()
        if data.get("starts_on") and data["starts_on"].year < dt.date.today().year:
            raise forms.ValidationError(
                {"starts_on": _("Creating absences for past years is not allowed.")}
            )
        return data
