from collections import namedtuple
from functools import lru_cache

from django.db import models
from django.utils.text import capfirst
from django.utils.translation import ugettext as _

from audit.models import LoggedAction


Change = namedtuple('Change', 'changes version number')


def boolean_formatter(value):
    if value in (True, 't'):
        return _('yes')
    elif value in (False, 'f'):
        return _('no')
    return value


def default_if_none(value, default):
    return default if value is None else value


@lru_cache()
def formatter(field):
    """
    Returns a formatter for the passed model field instance
    """
    if field.choices:
        choices = {str(key): value for key, value in field.flatchoices}
        return lambda value: default_if_none(
            choices.get(value, value),
            '<empty>')

    if field.related_model:
        model = field.related_model
        queryset = model._default_manager.all()

        def _fn(value):
            if value is None:
                return _('<no value>')

            try:
                return str(queryset.get(pk=value))
            except model.DoesNotExist:
                return _('Deleted %s instance') % model._meta.verbose_name

        return _fn

    if isinstance(field, (models.BooleanField, models.NullBooleanField)):
        return lambda value: boolean_formatter(value)

    return lambda value: default_if_none(value, _('<no value>'))


def changes(instance, fields):
    versions = LoggedAction.objects.for_instance(instance)
    changes = []

    field_instances = [instance._meta.get_field(f) for f in fields]

    values = versions[0].row_data
    version_changes = [
        _("Initial value of '%(field)s' was '%(current)s'.") % {
            'field': capfirst(f.verbose_name),
            'current': formatter(f)(values.get(f.name)),
        }
        for f in field_instances
        if not (f.many_to_many or f.one_to_many)  # Avoid those relation types.
    ]

    changes.append(Change(
        changes=version_changes,
        version=versions[0],
        number=1,
    ))

    for change in versions[1:]:
        version_changes = [
            _("'%(field)s' changed from '%(previous)s' to '%(current)s'.") % {
                'field': capfirst(f.verbose_name),
                'current': formatter(f)(change.changed_fields.get(f.name)),
                'previous': formatter(f)(change.row_data.get(f.name)),
            }
            for f in field_instances
            if f.name in change.changed_fields
        ]

        if version_changes:
            changes.append(Change(
                changes=version_changes,
                version=change,
                number=changes[-1].number + 1,
            ))

    return changes
