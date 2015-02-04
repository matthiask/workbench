from django import forms
from django.utils.text import capfirst
from django.utils.translation import ugettext_lazy as _

from deals.models import Funnel


class DealSearchForm(forms.Form):
    f = forms.ModelChoiceField(
        queryset=Funnel.objects.all(),
        required=False,
        empty_label=capfirst(_('all')),
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
