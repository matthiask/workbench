from datetime import date

from django import forms
from django.db.models import Q
from django.utils.html import format_html
from django.utils.translation import gettext as _

from workbench.expenses.models import ExpenseReport
from workbench.logbook.models import LoggedCost
from workbench.tools.formats import currency, local_date_format
from workbench.tools.forms import ModelForm


class ExpenseReportForm(ModelForm):
    user_fields = default_to_current_user = ["owned_by"]

    class Meta:
        model = ExpenseReport
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        assert not self.instance.closed_on, "Must be in preparation"
        self.fields["is_closed"] = forms.BooleanField(
            label=_("is closed"),
            help_text=_("Once an expense report is closed it stays that way."),
            required=False,
        )

        if self.instance.pk:
            self.fields["expenses"] = forms.ModelMultipleChoiceField(
                queryset=LoggedCost.objects.expenses(
                    user=self.instance.owned_by
                ).filter(
                    Q(expense_report=self.instance) | Q(expense_report__isnull=True)
                ),
                label=_("expenses"),
                widget=forms.CheckboxSelectMultiple,
            )
            self.fields["expenses"].initial = self.instance.expenses.values_list(
                "id", flat=True
            )
        else:
            self.instance.created_by = self.request.user
            self.instance.owned_by = self.request.user

            expenses = LoggedCost.objects.expenses(user=self.request.user).filter(
                expense_report__isnull=True
            )
            self.fields["expenses"] = forms.ModelMultipleChoiceField(
                queryset=expenses,
                label=_("expenses"),
                widget=forms.CheckboxSelectMultiple,
            )
            self.fields["expenses"].initial = expenses.values_list("id", flat=True)

        self.fields["expenses"].choices = [
            (
                cost.id,
                format_html(
                    "{}<br>{}{}<br>{}<br>{}",
                    local_date_format(cost.rendered_on),
                    cost.project,
                    (": %s" % cost.service) if cost.service else "",
                    cost.description,
                    currency(cost.third_party_costs),
                ),
            )
            for cost in self.fields["expenses"]
            .queryset.select_related("service", "project__owned_by")
            .order_by("rendered_on", "pk")
        ]

    def save(self):
        instance = super().save()
        instance.expenses.set(self.cleaned_data["expenses"])
        if self.cleaned_data.get("is_closed"):
            instance.closed_on = date.today()
        instance.save()
        return instance
