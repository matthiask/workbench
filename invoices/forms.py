from datetime import date
from decimal import Decimal

from django import forms
from django.db.models import Q
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _

from contacts.forms import PostalAddressSelectionForm
from contacts.models import Organization, Person
from invoices.models import Invoice
from tools.formats import local_date_format
from tools.forms import Picker, Textarea, WarningsForm
from workbench.templatetags.workbench import currency


class InvoiceSearchForm(forms.Form):
    s = forms.ChoiceField(
        choices=(
            ('', _('All states')),
            ('open', _('Open')),
            (_('Exact'), Invoice.STATUS_CHOICES),
        ),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    org = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        required=False,
        widget=Picker(model=Organization),
    )

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get('s') == 'open':
            queryset = queryset.filter(status__in=(
                Invoice.IN_PREPARATION,
                Invoice.SENT,
                Invoice.REMINDED,
            ))
        elif data.get('s'):
            queryset = queryset.filter(status=data.get('s'))
        if data.get('org'):
            queryset = queryset.filter(customer=data.get('org'))

        return queryset


class CreateInvoiceForm(PostalAddressSelectionForm):
    user_fields = default_to_current_user = ('owned_by',)

    class Meta:
        model = Invoice
        fields = (
            'contact', 'title', 'description', 'owned_by', 'type',
        )
        widgets = {
            'contact': Picker(model=Person),
            'type': forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project')
        kwargs['initial'] = {
            'title': self.project.title,
            'description': self.project.description,
            'contact': self.project.contact_id,
        }

        super().__init__(*args, **kwargs)

        self.instance.project = self.project
        self.instance.customer = self.project.customer
        self.instance.contact = self.project.contact

        self.fields['type'].choices = Invoice.TYPE_CHOICES

        self.add_postal_address_selection(
            organization=self.project.customer,
            person=self.project.contact)

    def clean(self):
        data = super().clean()
        if data.get('contact'):
            if data['contact'].organization != self.project.customer:
                raise forms.ValidationError({
                    'contact': _(
                        'Selected contact does not belong to project\'s'
                        ' organization, %(organization)s.'
                    ) % {'organization': self.project.customer},
                })
        return data

    def save(self):
        instance = super().save(commit=False)
        if self.cleaned_data.get('pa'):
            instance.postal_address = self.cleaned_data['pa'].postal_address
        instance.save()
        return instance


class InvoiceForm(WarningsForm, PostalAddressSelectionForm):
    user_fields = default_to_current_user = ('owned_by',)

    class Meta:
        model = Invoice
        fields = (
            'customer', 'contact', 'invoiced_on', 'due_on', 'title',
            'description', 'owned_by', 'status', 'postal_address',
            'type', 'discount', 'liable_to_vat',
        )
        widgets = {
            'customer': Picker(model=Organization),
            'contact': Picker(model=Person),
            'status': forms.RadioSelect,
            'description': Textarea,
            'postal_address': Textarea,
            'type': forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['type'].choices = Invoice.TYPE_CHOICES
        self.fields['type'].disabled = True

        if self.instance.project:
            del self.fields['customer']

        if self.instance.type in (
                self.instance.FIXED,
                self.instance.DOWN_PAYMENT):
            self.fields['subtotal'] = forms.DecimalField(
                label=(
                    _('Down payment')
                    if self.instance.type == Invoice.DOWN_PAYMENT
                    else _('subtotal')),
                max_digits=10,
                decimal_places=2,
                initial=self.instance.subtotal,
            )

        if (self.instance.type != Invoice.DOWN_PAYMENT and
                self.instance.project_id):
            eligible_down_payment_invoices = Invoice.objects.filter(
                Q(project=self.instance.project),
                Q(type=Invoice.DOWN_PAYMENT),
                Q(down_payment_applied_to__isnull=True) |
                Q(down_payment_applied_to=self.instance),
            )
            if eligible_down_payment_invoices:
                self.fields['apply_down_payment'] =\
                    forms.ModelMultipleChoiceField(
                        label=_('Apply down payment invoices'),
                        queryset=eligible_down_payment_invoices,
                        widget=forms.CheckboxSelectMultiple,
                        required=False,
                        initial=Invoice.objects.filter(
                            down_payment_applied_to=self.instance,
                        ).values_list('id', flat=True),
                    )
                self.fields['apply_down_payment'].choices = [
                    (
                        invoice.id,
                        format_html(
                            '{}<br/>{}, {}',
                            invoice.__html__(),
                            currency(invoice.total),
                            invoice.pretty_status(),
                        )
                    ) for invoice in eligible_down_payment_invoices
                ]

        elif self.instance.type in (self.instance.SERVICES,):
            pass
            """
            self.fields['services'] = forms.ModelMultipleChoiceField(
                queryset=Service.objects.filter(
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

        self.fields.move_to_end('discount')
        if 'apply_down_payment' in self.fields:
            self.fields.move_to_end('apply_down_payment')
        self.fields.move_to_end('liable_to_vat')

        if not self.instance.postal_address:
            self.add_postal_address_selection(person=self.instance.contact)

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

        if self.instance.project and data.get('contact'):
            if data['contact'].organization != self.instance.project.customer:
                raise forms.ValidationError({
                    'contact': _(
                        'Selected contact does not belong to project\'s'
                        ' organization, %(organization)s.'
                    ) % {'organization': self.instance.project.customer},
                })

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
                    'closed': local_date_format(
                        self.instance.closed_at, 'd.m.Y'),
                })

        return data

    def save(self):
        instance = super().save(commit=False)

        if instance.type in (instance.FIXED, instance.DOWN_PAYMENT):
            instance.subtotal = self.cleaned_data['subtotal']
            instance.down_payment_total = Decimal()

        if 'apply_down_payment' in self.cleaned_data:
            instance.down_payment_invoices.set(
                self.cleaned_data.get('apply_down_payment'))
            instance.down_payment_total = sum((
                invoice.total_excl_tax
                for invoice in self.cleaned_data.get('apply_down_payment')
            ), Decimal())

        instance.save()

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

        return instance


class CreatePersonInvoiceForm(PostalAddressSelectionForm):
    user_fields = default_to_current_user = ('owned_by',)
    type = forms.ChoiceField(
        label=_('type'),
        choices=Invoice.TYPE_CHOICES,
        initial=Invoice.FIXED,
        disabled=True,
        widget=forms.RadioSelect,
        help_text=_(
            'Other invoice types must be created directly on a project.'),
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
        initial.update({'subtotal': None})  # Invalid -- force input.

        person = None

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

        self.instance.type = Invoice.FIXED

        if person:
            self.add_postal_address_selection(person=person)
