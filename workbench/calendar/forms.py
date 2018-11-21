from collections import defaultdict
from datetime import date

from django import forms
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _

from workbench.accounts.models import User
from workbench.tools.forms import ModelForm, WarningsForm

from .models import Day, current_app


class DaySearchForm(forms.Form):
    year = forms.TypedChoiceField(
        choices=[(year, year) for year in range(2018, 2021)],
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        coerce=int,
    )

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("year"):
            return queryset.filter(day__year=data["year"])
        return queryset

    def response(self, request):
        if "year" not in request.GET:
            return HttpResponseRedirect("?year={}".format(date.today().year))


class DayForm(WarningsForm, ModelForm):
    user_fields = default_to_current_user = ["handled_by"]

    class Meta:
        model = Day
        fields = ["handled_by"]

    def _only_active_and_initial_users(self, formfield, pk):
        d = defaultdict(list)
        for user in User.objects.filter(
            Q(is_active=True, apps__slug=current_app) | Q(pk=pk)
        ):
            d[user.is_active].append(
                (formfield.prepare_value(user), formfield.label_from_instance(user))
            )
        choices = [(_("Active"), d.get(True, []))]
        if d.get(False):
            choices[0:0] = d.get(False)
        if not formfield.required:
            choices.insert(0, ("", "----------"))
        formfield.choices = choices

    def clean(self):
        data = super().clean()
        print(self.instance.handled_by, data.get("handled_by"))
        if self.instance.handled_by and self.request.user != self.instance.handled_by:
            self.add_warning(
                _(
                    "You are editing a day which is already handled by someone else."
                    " Are you sure this is correct?"
                )
            )
        return data
