from django import forms
from django.utils.translation import gettext as _

from workbench.expenses.models import ExpenseReport
from workbench.tools.forms import ModelForm


class ExpenseReportForm(ModelForm):
    user_fields = default_to_current_user = ["owned_by"]

    class Meta:
        model = ExpenseReport
        fields = ["owned_by"]

    def clean(self):
        data = super().clean()
        if (
            data.get("owned_by")
            and not ExpenseReport.objects.expenses_for(user=data["owned_by"]).exists()
        ):
            raise forms.ValidationError(
                {"owned_by": _("All expenses are bound to an expense report already.")}
            )
        return data

    def save(self):
        return ExpenseReport.objects.create_report(user=self.cleaned_data["owned_by"])
