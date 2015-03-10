from django import forms
from django.template.defaultfilters import linebreaksbr
from django.utils.translation import ugettext_lazy as _

from contacts.models import PostalAddress
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


class CreateOfferForm(ModelForm):
    user_fields = ('owned_by',)
    default_to_current_user = user_fields

    class Meta:
        model = Offer
        fields = (
            'title', 'description', 'owned_by',
        )

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project')
        kwargs['initial'] = {'title': self.project.title}

        super().__init__(*args, **kwargs)

        postal_addresses = []

        if self.project.contact:
            postal_addresses.extend(
                (pa.id, linebreaksbr(pa.postal_address))
                for pa in PostalAddress.objects.filter(
                    person=self.project.contact,
                )
            )

        postal_addresses.extend(
            (pa.id, linebreaksbr(pa.postal_address))
            for pa in PostalAddress.objects.filter(
                person__organization=self.project.customer,
            ).exclude(person=self.project.contact)
        )

        if postal_addresses:
            self.fields['pa'] = forms.ModelChoiceField(
                PostalAddress.objects.all(),
                label=_('postal address'),
                help_text=_('The exact address can be edited later.'),
                widget=forms.RadioSelect,
            )
            self.fields['pa'].choices = postal_addresses

    def save(self):
        instance = super().save(commit=False)
        if self.cleaned_data.get('pa'):
            instance.postal_address = self.cleaned_data['pa'].postal_address
        instance.project = self.project
        instance.save()
        return instance
