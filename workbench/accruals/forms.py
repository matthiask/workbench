from django import forms
from django.utils.translation import gettext_lazy as _

from workbench.accruals.models import CutoffDate
from workbench.tools.forms import ModelForm, WarningsForm


class CutoffDateSearchForm(forms.Form):
    def filter(self, queryset):
        return queryset


class CutoffDateForm(ModelForm, WarningsForm):
    class Meta:
        model = CutoffDate
        fields = ["day"]

    def clean(self):
        data = super().clean()
        if data.get("day"):
            if data["day"].day != 1:
                self.add_warning(_("Unusual cutoff date (not first of the month)."))
        return data
