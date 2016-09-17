# from django import forms
# from django.utils.translation import ugettext_lazy as _

from logbook.models import LoggedHours
from tools.forms import ModelForm, Textarea


class LoggedHoursForm(ModelForm):
    user_fields = default_to_current_user = ('rendered_by',)

    class Meta:
        model = LoggedHours
        fields = (
            'rendered_by', 'rendered_on', 'hours', 'description',
        )
        widgets = {
            'description': Textarea(),
        }

    def __init__(self, *args, **kwargs):
        self.task = kwargs.pop('task')
        super().__init__(*args, **kwargs)

    def save(self):
        instance = super().save(commit=False)
        if not instance.pk:
            instance.created_by = self.request.user
        instance.task = self.task
        instance.save()
        return instance
