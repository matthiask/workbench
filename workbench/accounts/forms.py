from django import forms
from django.conf import settings
from django.utils.translation import gettext as _

from workbench.accounts.models import User
from workbench.awt.models import WorkingTimeModel
from workbench.tools.forms import ModelForm


class UpdateUserForm(ModelForm):
    class Meta:
        model = User
        fields = ("_full_name", "_short_name", "email", "language")
        widgets = {"language": forms.RadioSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].disabled = True
        self.fields["email"].help_text = _(
            "Managed automatically. Contact your administrator to change this."
        )
        self.fields["language"].choices = settings.LANGUAGES


class CreateUserForm(ModelForm):
    class Meta:
        model = User
        fields = (
            "_full_name",
            "_short_name",
            "email",
            "language",
            "working_time_model",
        )
        widgets = {
            "language": forms.RadioSelect,
            "working_time_model": forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].disabled = True
        self.fields["email"].help_text = _(
            "Managed automatically. Contact your administrator to change this."
        )
        self.fields["language"].choices = settings.LANGUAGES
        self.fields["working_time_model"].choices = [
            (wtm.id, str(wtm)) for wtm in WorkingTimeModel.objects.all()
        ]
