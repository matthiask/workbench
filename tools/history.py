from collections import namedtuple

from django.utils.translation import ugettext as _

import reversion


Change = namedtuple('Change', 'changes version')


def changes(instance, fields):
    versions = reversion.get_for_object(instance)[::-1]
    changes = []
    for previous, update in zip(versions, versions[1:]):
        version_changes = []
        for field in fields:
            prev = previous.field_dict.get(field)
            curr = update.field_dict.get(field)

            if prev == curr:
                continue

            version_changes.append(
                _('"%(field)s" changed from "%(previous)s" to "%(current)s".')
                % {
                    'field': instance._meta.get_field(field).verbose_name,
                    'previous': prev,
                    'current': curr,
                }
            )

        changes.append(Change(
            changes=version_changes,
            version=update,
        ))
    return changes
