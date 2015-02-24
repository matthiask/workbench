from django import forms
# from django.utils.translation import ugettext_lazy as _, ugettext

from services.models import RenderedService
# from stories.models import Story


class RenderedServiceForm(forms.ModelForm):
    class Meta:
        model = RenderedService
        fields = (
            'rendered_on', 'rendered_by', 'hours', 'description',
        )
