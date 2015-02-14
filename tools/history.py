from collections import namedtuple

from django.utils.translation import ugettext as _

import reversion


Change = namedtuple('Change', 'changes version')


def changes(instance, fields):
    versions = reversion.get_for_object(instance)[::-1]
    changes = []
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
                _('"%(field)s" changed from "%(previous)s" to "%(current)s".')
                % {
                    'field': f.verbose_name,
                    'previous': prev,
                    'current': curr,
                }
            )

        changes.append(Change(
            changes=version_changes,
            version=current,
        ))
    return changes
