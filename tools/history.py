from collections import namedtuple
from functools import lru_cache

from django.utils.text import capfirst
from django.utils.translation import ugettext as _

from ftool.models import LoggedAction


Change = namedtuple('Change', 'changes version number')


@lru_cache()
def formatter(field):
    """
    Returns a formatter for the passed model field instance
    """
    if field.choices:
        choices = {str(key): value for key, value in field.flatchoices}
        return lambda value: choices.get(value, value)

    if field.related_model:
        model = field.related_model
        queryset = model._default_manager.all()

        def _fn(value):
            try:
                return str(queryset.get(pk=value))
            except model.DoesNotExist:
                return _('Deleted %s instance') % model._meta.verbose_name

        return _fn

    return lambda value: value


def changes(instance, fields):
    versions = LoggedAction.objects.for_instance(instance)
    changes = []

    field_instances = [instance._meta.get_field(f) for f in fields]

    values = versions[0].row_data
    version_changes = [
        _("Initial value of '%(field)s' was '%(current)s'.") % {
            'field': capfirst(f.verbose_name),
            'current': formatter(f)(values.get(f.attname)),
        }
        for f in field_instances
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
                'current': formatter(f)(change.changed_fields.get(f.attname)),
                'previous': formatter(f)(change.row_data.get(f.attname)),
            }
            for f in field_instances
            if f.attname in change.changed_fields
        ]

        if version_changes:
            changes.append(Change(
                changes=version_changes,
                version=change,
                number=changes[-1].number + 1,
            ))

    return changes
