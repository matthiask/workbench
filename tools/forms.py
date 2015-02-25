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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.user_fields:
            self._only_active_and_initial_users(
                self.fields[field],
                self.instance and getattr(
                    self.instance,
                    '%s_id' % field,
                    None)
            )

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
        formfield.choices = choices


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
        html = format_html('<input{} />', flatatt(final_attrs))

        instance = ''
        try:
            if value:
                instance = str(self.model.objects.get(pk=value))
        except self.model.DoesNotExist:
            pass

        id = attrs['id']
        opts = self.model._meta
        return mark_safe(''.join((
            html,
            '<a href="',
            reverse('%s_%s_picker' % (opts.app_label, opts.model_name)),
            '?id=',
            id,
            '" class="btn btn-default" data-toggle="ajaxmodal">Pick</a>',
            '<span id="',
            id,
            '_pretty">',
            escape(instance),
            '</span>',
        )))
