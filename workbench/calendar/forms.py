from collections import defaultdict
from datetime import date, timedelta

from django import forms
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _

from workbench.accounts.models import User
from workbench.tools.forms import ModelForm, WarningsForm

from .models import Day, current_app


def years():
    year = date.today().year
    return [("", _("year"))] + [(y, y) for y in range(year, year + 2)]


class DaySearchForm(forms.Form):
    year = forms.TypedChoiceField(
        choices=years,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        coerce=int,
    )

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("year"):
            return queryset.filter(day__year=data["year"])
        else:
            today = date.today()
            monday = today - timedelta(days=today.weekday())
            return queryset.filter(
                day__range=[monday - timedelta(days=7), monday + timedelta(days=7 * 12)]
            )


class DayForm(WarningsForm, ModelForm):
    user_fields = default_to_current_user = ["handled_by"]

    class Meta:
        model = Day
        fields = ["handled_by"]

    def _only_active_and_initial_users(self, formfield, pk):
        d = defaultdict(list)
        for user in User.objects.filter(
            Q(is_active=True, apps__slug=current_app) | Q(pk=pk)
        ).distinct():
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


class PresenceForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.app = kwargs.pop("instance")
        self.request = kwargs.pop("request")
        self.year = date.today().year
        super().__init__(*args, **kwargs)
        presences = {
            p.user_id: p.percentage for p in self.app.presences.filter(year=self.year)
        }

        for user in self.app.users.all():
            self.fields["presence_{}".format(user.id)] = forms.IntegerField(
                label=user.get_full_name(),
                required=False,
                initial=presences.get(user.id),
            )

    def save(self):
        to_delete = set()
        for user in self.app.users.all():
            value = self.cleaned_data.get("presence_{}".format(user.id))
            if value is None:
                to_delete.add(user.id)
            else:
                self.app.presences.update_or_create(
                    year=self.year, user=user, defaults={"percentage": value}
                )
        if to_delete:
            self.app.presences.filter(year=self.year, user__in=to_delete).delete()
        return self.app
