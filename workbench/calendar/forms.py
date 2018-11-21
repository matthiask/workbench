# from django import forms

from workbench.tools.forms import ModelForm

from .models import Day


class DayForm(ModelForm):
    user_fields = default_to_current_user = ["handled_by"]

    class Meta:
        model = Day
        fields = ["handled_by"]
