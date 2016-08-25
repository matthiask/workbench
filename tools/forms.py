from collections import defaultdict

from django import forms
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.forms.utils import flatatt
from django.utils.encoding import force_text
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext, ugettext_lazy as _

from accounts.models import User


class Textarea(forms.Textarea):
    def __init__(self, attrs=None):
        default_attrs = {'cols': 40, 'rows': 4}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)


class ModelForm(forms.ModelForm):
    user_fields = ()
    default_to_current_user = ()

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')

        if self.default_to_current_user:
            instance = kwargs.get('instance')
            if not instance or not instance.pk:
                initial = kwargs.setdefault('initial', {})
                for field in self.default_to_current_user:
                    initial.setdefault(field, self.request.user.pk)

        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            if isinstance(field, forms.DateField):
                css = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = css + ' datepicker'

            elif name in self.user_fields:
                self._only_active_and_initial_users(
                    field,
                    self.instance and getattr(
                        self.instance,
                        '%s_id' % name,
                        None)
                )

        self.customer_and_contact = all(
            f in self.fields for f in ('customer', 'contact'))
        if self.customer_and_contact:
            self.fields['customer'].required = False

    def _only_active_and_initial_users(self, formfield, pk):
        d = defaultdict(list)
        for user in User.objects.filter(Q(is_active=True) | Q(pk=pk)):
            d[user.is_active].append((
                formfield.prepare_value(user),
                formfield.label_from_instance(user),
            ))
        choices = [(_('Active'), d.get(True, []))]
        if d.get(False):
            choices[0:0] = d.get(False)
        if not formfield.required:
            choices.insert(0, ('', '----------'))
        formfield.choices = choices

    def clean(self):
        data = super().clean()

        if self.customer_and_contact:
            if data.get('contact') and not data.get('customer'):
                data['customer'] = data['contact'].organization

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

            if not data.get('customer'):
                raise forms.ValidationError({
                    'customer': self.fields['customer'].error_messages['required'],  # noqa
                }, code='required')

        return data


_PICKER_TEMPLATE = '''
<div class="input-group">
  <a href="%(url)s" class="btn btn-default input-group-addon"
      data-toggle="ajaxmodal">
    <span class="glyphicon glyphicon-search"></span>
  </a>
  <input type="text" class="form-control" id="%(id)s_pretty"
    value="%(pretty)s" disabled>
  %(field)s
</div>
'''


class Picker(forms.TextInput):
    def __init__(self, model, attrs=None):
        super().__init__(attrs)
        self.model = model

    def render(self, name, value, attrs=None, choices=()):
        if value is None:
            value = ''
        final_attrs = self.build_attrs(attrs, type='hidden', name=name)
        if value != '':
            # Only add the 'value' attribute if a value is non-empty.
            final_attrs['value'] = force_text(self._format_value(value))

        pretty = ''
        try:
            if value:
                pretty = str(self.model.objects.get(pk=value))
        except (self.model.DoesNotExist, TypeError, ValueError):
            pass

        opts = self.model._meta

        return mark_safe(_PICKER_TEMPLATE % {
            'id': final_attrs['id'],
            'url': '%s?id=%s' % (
                reverse('%s_%s_picker' % (opts.app_label, opts.model_name)),
                final_attrs['id'],
            ),
            'field': format_html('<input{} />', flatatt(final_attrs)),
            'pretty': escape(pretty),
        })


class WarningsForm(forms.BaseForm):
    """
    Form subclass which allows implementing validation warnings
    In contrast to Django's ``ValidationError``, these warnings may
    be ignored by checking a checkbox.
    The warnings support consists of the following methods and properties:
    * ``WarningsForm.add_warning(<warning>)``: Adds a new warning message
    * ``WarningsForm.warnings``: A list of warnings or an empty list if there
      are none.
    * ``WarningsForm.is_valid()``: Overridden ``Form.is_valid()``
      implementation which returns ``False`` for otherwise valid forms with
      warnings, if those warnings have not been explicitly ignored (by checking
      a checkbox or by passing ``ignore_warnings=True`` to ``is_valid()``.
    * An additional form field named ``ignore_warnings`` is available - this
      field should only be displayed if ``WarningsForm.warnings`` is non-emtpy.
    """
    def __init__(self, *args, **kwargs):
        super(WarningsForm, self).__init__(*args, **kwargs)

        self.warnings = []

    def add_warning(self, warning):
        """
        Adds a new warning, should be called while cleaning the data
        """
        self.warnings.append(warning)

    def is_valid(self, ignore_warnings=False):
        """
        ``is_valid()`` override which returns ``False`` for forms with warnings
        if these warnings haven't been explicitly ignored
        """
        if not super(WarningsForm, self).is_valid():
            return False

        if self.warnings and not self.request.POST.get('ignore_warnings'):
            return False

        return True
