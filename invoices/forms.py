from django import forms
from django.utils.translation import ugettext_lazy as _

from invoices.models import Invoice
from tools.forms import ModelForm


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


class InvoiceForm(ModelForm):
    user_fields = default_to_current_user = ('owned_by',)

    class Meta:
        model = Invoice
        fields = (
            'invoiced_on', 'due_on', 'title', 'description', 'owned_by',
            'status', 'postal_address',
        )

    def _inactive__init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['stories'].queryset = self.instance.project.stories.all()

    def _inactive_save(self):
        instance = super().save(commit=False)
        # Leave out save_m2m by purpose.
        instance.clear_stories(save=False)
        instance.add_stories(
            self.cleaned_data.get('stories'),
            save=True)
        return instance
