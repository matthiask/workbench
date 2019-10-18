import re
from collections import namedtuple
from functools import lru_cache

from django.db import models
from django.urls import reverse
from django.utils import dateparse
from django.utils.html import conditional_escape, format_html, mark_safe
from django.utils.text import capfirst
from django.utils.translation import gettext as _

from workbench.accounts.models import User
from workbench.tools.formats import local_date_format


Change = namedtuple("Change", "changes version")


def boolean_formatter(value):
    if value in {True, "t"}:
        return _("yes")
    elif value in {False, "f"}:
        return _("no")
    return value


def default_if_none(value, default):
    return default if value is None else value


def date_formatter(value):
    if value is None:
        return _("<no value>")
    dt = dateparse.parse_datetime(value) or dateparse.parse_date(value)
    return local_date_format(dt) if dt else value


@lru_cache()
def formatter(field):
    """
    Returns a formatter for the passed model field instance
    """
    if field.choices:
        choices = {str(key): value for key, value in field.flatchoices}
        return lambda value: default_if_none(choices.get(value, value), "<empty>")

    if field.related_model:
        model = field.related_model
        queryset = model._default_manager.all()

        def _fn(value):
            if value is None:
                return _("<no value>")

            try:
                pretty = str(queryset.get(pk=value))
            except model.DoesNotExist:
                pretty = _("Deleted %s instance") % model._meta.verbose_name

            return format_html(
                '<a href="{}" data-toggle="ajaxmodal">{}</a>',
                reverse("history", args=(model._meta.db_table, "id", value)),
                pretty,
            )

        return _fn

    if isinstance(field, (models.BooleanField, models.NullBooleanField)):
        return boolean_formatter

    if isinstance(field, models.DateField):
        return date_formatter

    return lambda value: default_if_none(value, _("<no value>"))


def changes(model, fields, actions):
    changes = []

    if not actions:
        return changes

    users = {str(u.pk): u.get_full_name() for u in User.objects.all()}
    for action in actions:
        match = re.search(r"^user-([0-9]+)-", action.user_name)
        if match:
            pk = match.groups()[0]
            action.pretty_user_name = users.get(pk) or action.user_name
        else:
            action.pretty_user_name = action.user_name

    for action in actions:
        if action.action == "I":
            values = action.row_data
            version_changes = [
                mark_safe(
                    _("Initial value of '%(field)s' was '%(current)s'.")
                    % {
                        "field": conditional_escape(capfirst(f.verbose_name)),
                        "current": conditional_escape(
                            formatter(f)(values.get(f.attname))
                        ),
                    }
                )
                for f in fields
                if not (f.many_to_many or f.one_to_many)  # Avoid those relation types.
            ]

        elif action.action == "U":
            values = action.changed_fields or {}
            version_changes = [
                mark_safe(
                    _("New value of '%(field)s' was '%(current)s'.")
                    % {
                        "field": conditional_escape(capfirst(f.verbose_name)),
                        "current": conditional_escape(
                            formatter(f)(values.get(f.attname))
                        ),
                    }
                )
                for f in fields
                if f.attname in values
            ]

        else:  # Deletion or truncation
            values = action.row_data
            version_changes = [
                mark_safe(
                    _("Final value of '%(field)s' was '%(current)s'.")
                    % {
                        "field": conditional_escape(capfirst(f.verbose_name)),
                        "current": conditional_escape(
                            formatter(f)(values.get(f.attname))
                        ),
                    }
                )
                for f in fields
                if not (f.many_to_many or f.one_to_many)  # Avoid those relation types.
            ]

        if version_changes:
            changes.append(Change(changes=version_changes, version=action))

    return changes
