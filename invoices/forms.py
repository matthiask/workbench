from datetime import date

from django import forms
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import ugettext_lazy as _

from contacts.models import Organization, Person
from invoices.models import Invoice
from tools.forms import ModelForm, Picker, Textarea, WarningsForm


class InvoiceSearchForm(forms.Form):
    s = forms.ChoiceField(
        choices=(('', _('All states')),) + Invoice.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    org = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        required=False,
        widget=Picker(model=Organization),
    )

    def filter(self, queryset):
        if not self.is_valid():
            return queryset

        data = self.cleaned_data
        if data.get('s'):
            queryset = queryset.filter(status=data.get('s'))
        if data.get('org'):
            queryset = queryset.filter(customer=data.get('org'))

        return queryset


class InvoiceForm(WarningsForm, ModelForm):
    user_fields = default_to_current_user = ('owned_by',)

    class Meta:
        model = Invoice
        fields = (
            'customer', 'contact', 'invoiced_on', 'due_on', 'title',
            'description', 'owned_by', 'status', 'postal_address',
        )
        widgets = {
            'customer': Picker(model=Organization),
            'contact': Picker(model=Person),
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
            pass
            """
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
            """

        if 'ignore_warnings' in self.fields:
            self.fields.move_to_end('ignore_warnings', last=False)

    def _is_status_unexpected(self, to_status):
        if not to_status:
            return False

        from_status = self.instance._orig_status

        if from_status == to_status:
            return False
        if from_status > to_status or from_status >= Invoice.PAID:
            return True
        return False

    def clean(self):
        data = super().clean()
        s_dict = dict(Invoice.STATUS_CHOICES)

        if self.instance._orig_status < self.instance.SENT:
            invoiced_on = data.get('invoiced_on')
            if invoiced_on and invoiced_on < date.today():
                self.add_warning(_(
                    'Invoice date is in the past, but invoice is still'
                    ' in preparation. Are you sure you do not want to'
                    ' set the invoice date to today?'
                ))

        if self.instance.status > self.instance.IN_PREPARATION:
            if (set(self.changed_data) - {'status'}):
                self.add_warning(_(
                    'You are attempting to change %(fields)s.'
                    ' I am trying to prevent unintentional changes to'
                    ' anything but the status field.'
                    ' Are you sure?'
                ) % {
                    'fields': ', '.join(
                        "'%s'" % self.fields[field].label
                        for field in self.changed_data
                    ),
                })

        if self._is_status_unexpected(data.get('status')):
            self.add_warning(_(
                "Moving status from '%(from)s' to '%(to)s'."
                " Are you sure?"
            ) % {
                'from': s_dict[self.instance._orig_status],
                'to': s_dict[data['status']],
            })

        if data.get('status', 0) >= Invoice.PAID:
            if not self.instance.closed_at:
                self.instance.closed_at = timezone.now()

        if self.instance.closed_at and data.get('status', 99) < Invoice.PAID:
            if self.request.POST.get('ignore_warnings'):
                self.instance.closed_at = None
            else:
                self.add_warning(_(
                    "You are attempting to set status to '%(to)s',"
                    " but the invoice has already been closed on %(closed)s."
                    " Are you sure?"
                ) % {
                    'to': s_dict[data['status']],
                    'closed': date_format(self.instance.closed_at, 'd.m.Y'),
                })

        return data

    def save(self):
        instance = super().save(commit=False)

        if instance.type in (instance.FIXED, instance.DOWN_PAYMENT):
            instance.subtotal = self.cleaned_data['subtotal']
            instance.save()

        elif instance.type in (self.instance.SERVICES,):
            # Leave out save_m2m by purpose.
            instance.clear_stories(save=False)
            instance.add_stories(
                self.cleaned_data.get('stories'),
                save=True)

            self.cleaned_data.get('services').update(
                invoice=instance,
                archived_at=timezone.now(),
            )

        return instance


class CreatePersonInvoiceForm(ModelForm):
    user_fields = default_to_current_user = ('owned_by',)
    type = forms.ChoiceField(
        label=_('type'),
        choices=Invoice.TYPE_CHOICES,
        initial=Invoice.FIXED,
        disabled=True,
        widget=forms.RadioSelect,
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
        initial = kwargs.setdefault('initial', {})
        initial.update({'invoiced_on': date.today(), 'subtotal': None})

        if request.GET.get('person'):
            try:
                person = Person.objects.get(pk=request.GET.get('person'))
            except (Person.DoesNotExist, TypeError, ValueError):
                pass
            else:
                initial.update({
                    'customer': person.organization,
                    'contact': person,
                })

        super().__init__(*args, **kwargs)

    def save(self):
        instance = super().save(commit=False)
        instance.type = instance.FIXED
        pa = instance.contact and instance.contact.postaladdresses.first()
        if pa:
            instance.postal_address = pa.postal_address
        instance.save()
        return instance
