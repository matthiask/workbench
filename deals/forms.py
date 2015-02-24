from django import forms
from django.utils.translation import ugettext_lazy as _

from deals.models import Funnel, Deal
from tools.forms import ModelForm


class DealSearchForm(forms.Form):
    f = forms.ModelChoiceField(
        queryset=Funnel.objects.all(),
        required=False,
        empty_label=_('All funnels'),
        widget=forms.Select(attrs={'class': 'form-control'}),
    )


class DealForm(ModelForm):
    user_fields = ('owned_by',)

    class Meta:
        model = Deal
        fields = (
            'funnel', 'title', 'description', 'owned_by', 'estimated_value')
