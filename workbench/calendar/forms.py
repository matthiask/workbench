from collections import defaultdict

from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
# from django import forms

from workbench.accounts.models import User
from workbench.tools.forms import ModelForm

from .models import Day, current_app


class DayForm(ModelForm):
    user_fields = default_to_current_user = ["handled_by"]

    class Meta:
        model = Day
        fields = ["handled_by"]

    def _only_active_and_initial_users(self, formfield, pk):
        d = defaultdict(list)
        for user in User.objects.filter(Q(is_active=True, apps__slug=current_app) | Q(pk=pk)):
            d[user.is_active].append(
                (formfield.prepare_value(user), formfield.label_from_instance(user))
            )
        choices = [(_("Active"), d.get(True, []))]
        if d.get(False):
            choices[0:0] = d.get(False)
        if not formfield.required:
            choices.insert(0, ("", "----------"))
        formfield.choices = choices
