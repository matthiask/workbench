from workbench.expenses.models import ExpenseReport
from workbench.tools.forms import ModelForm


class ExpenseReportForm(ModelForm):
    user_fields = default_to_current_user = ["owned_by"]

    class Meta:
        model = ExpenseReport
        fields = ["owned_by"]
