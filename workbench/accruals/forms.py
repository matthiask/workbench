# from django import forms

from workbench.accruals.models import Accrual
from workbench.tools.forms import ModelForm


class AccrualForm(ModelForm):
    class Meta:
        model = Accrual
        fields = ["invoice", "month", "accrual"]
