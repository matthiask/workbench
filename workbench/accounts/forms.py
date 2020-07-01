from django import forms
from django.conf import settings
from django.utils.translation import gettext as _

from workbench.accounts.models import User
from workbench.awt.models import WorkingTimeModel
from workbench.tools.forms import Form, ModelForm


class UserSearchForm(Form):
    def filter(self, queryset):
        return queryset.filter(is_active=True)


class UserForm(ModelForm):
    class Meta:
        model = User
        fields = (
            "_full_name",
            "_short_name",
            "language",
            "email",
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
            "Contact your administrator to change this value."
        )
        self.fields["language"].choices = settings.LANGUAGES
        self.fields["working_time_model"].choices = [
            (wtm.id, str(wtm)) for wtm in WorkingTimeModel.objects.all()
        ]

        if self.instance.pk:
            self.fields["working_time_model"].disabled = True
            self.fields["working_time_model"].help_text = _(
                "Contact your administrator to change this value."
            )
