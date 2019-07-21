from django import forms
from django.utils.translation import gettext as _

from workbench.accounts.models import User
from workbench.tools.forms import ModelForm


class UserForm(ModelForm):
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
