from collections import namedtuple

from django.utils.text import capfirst
from django.utils.translation import ugettext as _

import reversion


Change = namedtuple('Change', 'changes version number')


def single_change(previous_object, current_object, field):
    f = current_object._meta.get_field(field)
    choices = {}
    if f.choices:
        choices = dict(f.flatchoices)

    curr = getattr(current_object, field)

    if previous_object is None:
        return _(
            "Initial value of '%(field)s' was '%(current)s'."
        ) % {
            'field': capfirst(f.verbose_name),
            'current': choices.get(curr, curr),
        }

    else:
        prev = getattr(previous_object, field)
        if prev == curr:
            return None

        return _(
            "'%(field)s' changed from '%(previous)s' to '%(current)s'."
        ) % {
            'field': capfirst(f.verbose_name),
            'current': choices.get(curr, curr),
            'previous': choices.get(prev, prev),
        }


def changes(instance, fields):
    versions = reversion.get_for_object(instance)[::-1]
    changes = []

    current_object = versions[0].object_version.object
    version_changes = [change for change in (
        single_change(None, current_object, field)
        for field in fields
    ) if change]

    changes.append(Change(
        changes=version_changes,
        version=versions[0],
        number=1,
    ))

    for previous, current in zip(versions, versions[1:]):
        previous_object = previous.object_version.object
        current_object = current.object_version.object

        version_changes = [change for change in (
            single_change(previous_object, current_object, field)
            for field in fields
        ) if change]

        changes.append(Change(
            changes=version_changes,
            version=current,
            number=changes[-1].number + 1,
        ))

    return changes
