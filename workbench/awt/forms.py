from django import forms, http
from django.utils.translation import ugettext_lazy as _

from workbench.accounts.models import User
from workbench.awt.models import Absence
from workbench.tools.forms import ModelForm, Textarea


class AbsenceSearchForm(forms.Form):
    u = forms.TypedChoiceField(
        label=_("user"),
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["u"].choices = [
            ("", _("All users")),
            (
                _("Active"),
                [
                    (u.id, u.get_full_name())
                    for u in User.objects.filter(is_active=True)
                ],
            ),
        ]

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("u"):
            queryset = queryset.filter(user=data.get("u"))
        return queryset

    def response(self, request):
        if "u" not in request.GET:
            return http.HttpResponseRedirect("?u={}".format(request.user.id))


class AbsenceForm(ModelForm):
    user_fields = default_to_current_user = ("user",)

    class Meta:
        model = Absence
        fields = ["user", "starts_on", "days", "description", "is_vacation"]
        widgets = {"description": Textarea}
