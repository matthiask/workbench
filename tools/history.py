from collections import namedtuple

from django.utils.text import capfirst
from django.utils.translation import ugettext as _

from ftool.models import LoggedAction


Change = namedtuple('Change', 'changes version number')


def single_change(model, previous_object, current_object, field):
    f = model._meta.get_field(field)
    choices = None
    queryset = None

    if f.choices:
        choices = {str(key): value for key, value in f.flatchoices}
    if f.related_model:
        queryset = f.related_model._default_manager.all()

    def format(value):
        if choices is not None:
            print(repr(choices), repr(value))
            return choices.get(value, value)
        if queryset is not None:
            return str(queryset.get(pk=value))
        return value

    curr = current_object.get(f.attname)

    if previous_object is None:
        return _(
            "Initial value of '%(field)s' was '%(current)s'."
        ) % {
            'field': capfirst(f.verbose_name),
            'current': format(curr),
        }

    else:
        prev = previous_object.get(f.attname)
        if prev == curr:
            return None

        return _(
            "'%(field)s' changed from '%(previous)s' to '%(current)s'."
        ) % {
            'field': capfirst(f.verbose_name),
            'current': format(curr),
            'previous': format(prev),
        }


def changes(instance, fields):
    versions = LoggedAction.objects.for_instance(instance)
    changes = []

    current_object = versions[0].row_data
    version_changes = [change for change in (
        single_change(instance, None, current_object, field)
        for field in fields
    ) if change]

    changes.append(Change(
        changes=version_changes,
        version=versions[0],
        number=1,
    ))

    for change in versions[1:]:
        changed_fields = set(change.changed_fields.keys())
        changed_fields.discard('fts_document')

        version_changes = [change for change in (
            single_change(
                instance,
                {field: change.row_data.get(field)},
                {field: change.changed_fields.get(field)},
                field,
            ) for field in changed_fields
        ) if change]

        changes.append(Change(
            changes=version_changes,
            version=change,
            number=changes[-1].number + 1,
        ))

    return changes
