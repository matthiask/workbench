from django import forms
from django.utils.translation import ugettext, ugettext_lazy as _

from contacts.models import Organization, Person
from offers.models import Offer
from tools.forms import ModelForm, Picker


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
        fields = ('customer', 'contact', 'title', 'description', 'owned_by')
        widgets = {
            'customer': Picker(model=Organization),
            'contact': Picker(model=Person),
        }

    def clean(self):
        data = super().clean()
        if data.get('customer') and data.get('contact'):
            if data.get('customer') != data.get('contact').organization:
                raise forms.ValidationError({
                    'contact': ugettext(
                        'The contact %(person)s does not belong to'
                        '  %(organization)s.'
                    ) % {
                        'person': data.get('contact'),
                        'organization': data.get('customer'),
                    },
                })
        return data
