from datetime import date

from django import forms
from django.utils.translation import gettext_lazy as _

from workbench.accruals.models import CutoffDate
from workbench.tools.forms import ModelForm


class CutoffDateSearchForm(forms.Form):
    def filter(self, queryset):
        return queryset


class CutoffDateForm(ModelForm):
    class Meta:
        model = CutoffDate
        fields = ["day"]

    def clean(self):
        data = super().clean()
        if data.get("day") and data["day"] > date.today():
            raise forms.ValidationError(
                {"day": _("Cannot create a cutoff date in the future.")}
            )
        return data
