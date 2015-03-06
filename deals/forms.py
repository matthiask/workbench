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

    def filter(self, queryset):
        if not self.is_valid():
            return queryset

        data = self.cleaned_data
        if data.get('f'):
            queryset = queryset.filter(funnel=data.get('f'))

        return queryset


class DealForm(ModelForm):
    user_fields = ('owned_by',)
    default_to_current_user = user_fields

    class Meta:
        model = Deal
        fields = (
            'funnel', 'title', 'description', 'owned_by', 'estimated_value',
            'status')
        widgets = {
            'status': forms.RadioSelect,
        }
