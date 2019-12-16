import datetime as dt

from django import forms, http
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.awt.models import Absence
from workbench.tools.forms import ModelForm, Textarea


class AbsenceSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("search")}
        ),
        label="",
    )
    u = forms.TypedChoiceField(
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["u"].choices = User.objects.choices(collapse_inactive=False)

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("u"):
            queryset = queryset.filter(user=data.get("u"))
        return queryset.select_related("user")

    def response(self, request, queryset):
        if "u" not in request.GET:
            return http.HttpResponseRedirect("?u={}".format(request.user.id))


class AbsenceForm(ModelForm):
    user_fields = default_to_current_user = ("user",)

    class Meta:
        model = Absence
        fields = ["user", "starts_on", "days", "description", "is_vacation"]
        widgets = {"description": Textarea({"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["days"].help_text = format_html(
            '<a href="#" data-hours-button="{hours}">{hours}</a>',
            hours=_("Enter hours"),
        )

    def clean(self):
        data = super().clean()
        if data.get("starts_on") and data["starts_on"].year < dt.date.today().year:
            raise forms.ValidationError(
                {"starts_on": _("Creating absences for past years is not allowed.")}
            )
        return data
