import datetime as dt

from django import forms
from django.db.models import Q
from django.utils.html import format_html
from django.utils.translation import gettext as _

from workbench.accounts.models import User
from workbench.expenses.models import ExpenseReport
from workbench.logbook.models import LoggedCost
from workbench.tools.formats import currency, local_date_format
from workbench.tools.forms import Form, ModelForm


class ExpenseReportSearchForm(Form):
    s = forms.ChoiceField(
        choices=[
            ("", _("All")),
            (
                _("status"),
                [("in-preparation", _("In preparation")), ("closed", _("Closed"))],
            ),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )
    owned_by = forms.TypedChoiceField(
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owned_by"].choices = User.objects.choices(
            collapse_inactive=True, myself=True
        )

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("s") == "in-preparation":
            queryset = queryset.filter(closed_on__isnull=True)
        elif data.get("s") == "closed":
            queryset = queryset.filter(closed_on__isnull=False)
        queryset = self.apply_owned_by(queryset)
        return queryset.select_related("owned_by")


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
                    "{}<br>{}: {}<br>{}<br>{}{}",
                    local_date_format(cost.rendered_on),
                    cost.service.project,
                    cost.service,
                    cost.description,
                    currency(cost.third_party_costs),
                    " ({} {})".format(cost.expense_currency, cost.expense_cost)
                    if cost.expense_cost
                    else "",
                ),
            )
            for cost in self.fields["expenses"]
            .queryset.select_related("service__project__owned_by")
            .order_by("rendered_on", "pk")
        ]

    def save(self):
        instance = super().save()
        instance.expenses.set(self.cleaned_data["expenses"])
        if self.cleaned_data.get("is_closed"):
            instance.closed_on = dt.date.today()
        instance.save()
        return instance
