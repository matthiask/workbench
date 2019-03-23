from django import forms
from django.utils.translation import gettext_lazy as _

from workbench.contacts.models import Organization, Person
from workbench.deals.models import Deal, Stage
from workbench.tools.forms import ModelForm, Picker


class DealSearchForm(forms.Form):
    s = forms.ChoiceField(
        choices=(
            ("all", _("All states")),
            ("", _("Open")),
            (_("Exact"), Deal.STATUS_CHOICES),
        ),
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
    )

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("s") == "":
            queryset = queryset.filter(status=Deal.OPEN)
        elif data.get("s") != "all":
            queryset = queryset.filter(status=data.get("s"))

        return queryset.select_related(
            "stage", "owned_by", "customer", "contact__organization"
        )


class DealForm(ModelForm):
    user_fields = default_to_current_user = ("owned_by",)

    stage = forms.ModelChoiceField(
        queryset=Stage.objects.all(),
        label=_("stage"),
        empty_label=None,
        widget=forms.RadioSelect,
    )

    class Meta:
        model = Deal
        fields = (
            "customer",
            "contact",
            "title",
            "description",
            "stage",
            "owned_by",
            "estimated_value",
            "status",
        )
        widgets = {
            "customer": Picker(model=Organization),
            "contact": Picker(model=Person),
            "status": forms.RadioSelect,
        }
