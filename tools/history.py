from collections import namedtuple

from django.utils.text import capfirst
from django.utils.translation import ugettext as _

import reversion


Change = namedtuple('Change', 'changes version number')


def changes(instance, fields):
    versions = reversion.get_for_object(instance)[::-1]
    changes = []
    version_changes = []
    current_object = versions[0].object_version.object

    for field in fields:
        curr = getattr(current_object, field)
        f = instance._meta.get_field(field)

        version_changes.append(
            _("Initial value of '%(field)s' was '%(current)s'.")
            % {
                'field': capfirst(f.verbose_name),
                'current': curr,
            }
        )

    changes.append(Change(
        changes=version_changes,
        version=versions[0],
        number=1,
    ))

    for previous, current in zip(versions, versions[1:]):
        version_changes = []
        previous_object = previous.object_version.object
        current_object = current.object_version.object

        for field in fields:
            prev = getattr(previous_object, field)
            curr = getattr(current_object, field)

            if prev == curr:
                continue

            f = instance._meta.get_field(field)

            # Handle choice fields
            if f.choices:
                d = dict(f.flatchoices)
                prev = d.get(prev, prev)
                curr = d.get(curr, curr)

            version_changes.append(
                _("'%(field)s' changed from '%(previous)s' to '%(current)s'.")
                % {
                    'field': capfirst(f.verbose_name),
                    'previous': prev,
                    'current': curr,
                }
            )

        changes.append(Change(
            changes=version_changes,
            version=current,
            number=changes[-1].number + 1,
        ))

    return changes
