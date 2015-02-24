from django import forms
# from django.utils.translation import ugettext_lazy as _, ugettext

from services.models import RenderedService
from tools.forms import ModelForm
# from stories.models import Story


class RenderedServiceForm(ModelForm):
    user_fields = ('rendered_by',)

    class Meta:
        model = RenderedService
        fields = (
            'rendered_on', 'rendered_by', 'hours', 'description',
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
