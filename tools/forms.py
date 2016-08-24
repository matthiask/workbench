from collections import defaultdict

from django import forms
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.forms.utils import flatatt
from django.utils.encoding import force_text
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

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

        for field in self.user_fields:
            self._only_active_and_initial_users(
                self.fields[field],
                self.instance and getattr(
                    self.instance,
                    '%s_id' % field,
                    None)
            )

        for name, field in self.fields.items():
            if isinstance(field, forms.DateField):
                css = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = css + ' datepicker'

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
