from django import forms
from django.utils.translation import ugettext_lazy as _

from offers.models import Offer
from tools.forms import ModelForm


class OfferSearchForm(forms.Form):
    s = forms.ChoiceField(
        choices=(('', _('All states')),) + Offer.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    def filter(self, queryset):
        if not self.is_valid():
            return queryset

        data = self.cleaned_data
        if data.get('s'):
            queryset = queryset.filter(status=data.get('s'))

        return queryset


class OfferForm(ModelForm):
    user_fields = ('owned_by',)
    default_to_current_user = user_fields

    class Meta:
        model = Offer
        fields = (
            'offered_on', 'title', 'description', 'owned_by', 'status',
            'postal_address')
        widgets = {
            'status': forms.RadioSelect,
        }
