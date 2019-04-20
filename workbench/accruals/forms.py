from datetime import timedelta

from django.utils.translation import gettext_lazy as _

from workbench.accruals.models import CutoffDate
from workbench.tools.forms import ModelForm


class CutoffDateForm(ModelForm):
    class Meta:
        model = CutoffDate
        fields = ["day"]

    def clean(self):
        data = super().clean()
        if data.get("day"):
            if (data["day"] + timedelta(days=1)).day != 1:
                self.add_warning(
                    _("Unusual cutoff date (not last of the month)."),
                    code="unusual-cutoff",
                )
        return data
