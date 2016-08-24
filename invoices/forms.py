from datetime import date

from django import forms
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from contacts.models import Organization, Person
from invoices.models import Invoice
from stories.models import RenderedService
from tools.forms import ModelForm, Picker, Textarea


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
        widgets = {
            'status': forms.RadioSelect,
            'description': Textarea,
            'postal_address': Textarea,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.type in (
                self.instance.FIXED,
                self.instance.DOWN_PAYMENT):
            self.fields['subtotal'] = forms.DecimalField(
                label=_('subtotal'),
                max_digits=10,
                decimal_places=2,
                initial=self.instance.subtotal,
            )

        elif self.instance.type in (self.instance.SERVICES,):
            self.fields['services'] = forms.ModelMultipleChoiceField(
                queryset=RenderedService.objects.filter(
                    Q(story__project=self.instance.project),
                    Q(
                        invoice=None,
                        archived_at__isnull=False,
                    ) | Q(invoice=self.instance),
                ),
                widget=forms.CheckboxSelectMultiple,
                initial=RenderedService.objects.filter(invoice=self.instance),
                label=_('rendered services'),
            )

    def save(self):
        instance = super().save(commit=False)

        if instance.type in (self.instance.SERVICES,):
            # Leave out save_m2m by purpose.
            instance.clear_stories(save=False)
            instance.add_stories(
                self.cleaned_data.get('stories'),
                save=True)

            self.cleaned_data.get('services').update(
                invoice=instance,
                archived_at=timezone.now(),
            )
        else:
            instance.save()

        return instance


class CreatePersonInvoiceForm(ModelForm):
    user_fields = default_to_current_user = ('owned_by',)
    type = forms.ChoiceField(
        label=_('type'),
        choices=Invoice.TYPE_CHOICES,
        initial=Invoice.FIXED,
        disabled=True,
    )

    class Meta:
        model = Invoice
        fields = (
            'customer', 'contact', 'invoiced_on', 'due_on', 'title',
            'description', 'owned_by', 'subtotal'
        )
        widgets = {
            'customer': Picker(model=Organization),
            'contact': Picker(model=Person),
        }

    def __init__(self, *args, **kwargs):
        request = kwargs['request']
        if request.GET.get('person'):
            person = Person.objects.get(pk=request.GET.get('person'))
            kwargs.setdefault('initial', {}).update({
                'customer': person.organization,
                'contact': person,
                'invoiced_on': date.today(),
                'subtotal': None,
            })

        super().__init__(*args, **kwargs)

    def save(self):
        instance = super().save(commit=False)
        instance.type = instance.FIXED
        instance.save()
        return instance
