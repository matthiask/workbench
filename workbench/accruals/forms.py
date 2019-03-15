from django import forms

from workbench.accruals.models import Accrual
from workbench.invoices.models import Invoice
from workbench.tools.forms import ModelForm, Picker


class AccrualSearchForm(forms.Form):
    def filter(self, queryset):
        return queryset.select_related("invoice__owned_by", "invoice__project")


class AccrualForm(ModelForm):
    class Meta:
        model = Accrual
        fields = ["invoice", "month", "accrual"]
        widgets = {"invoice": Picker(model=Invoice)}
