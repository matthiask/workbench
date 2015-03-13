from django import forms
from django.utils.translation import ugettext_lazy as _

from invoices.models import Invoice


class InvoiceSearchForm(forms.Form):
    s = forms.ChoiceField(
        choices=(('', _('All states')),) + Invoice.STATUS_CHOICES,
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
