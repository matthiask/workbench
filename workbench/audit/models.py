import re

from django.contrib.postgres.fields import HStoreField
from django.db import models
from django.db.models import Q
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _


class LoggedActionQuerySet(models.QuerySet):
    def for_model(self, model):
        return self.filter(table_name=model._meta.db_table)

    def with_data(self, **kwargs):
        queryset = self
        for key, value in kwargs.items():
            queryset = queryset.filter(
                Q(**{"row_data__%s" % key: value})
                | Q(**{"changed_fields__%s" % key: value})
            )
        return queryset


class LoggedAction(models.Model):
    ACTION_TYPES = (
        ("I", "INSERT"),
        ("U", "UPDATE"),
        ("D", "DELETE"),
        ("T", "TRUNCATE"),
    )

    event_id = models.IntegerField(primary_key=True)
    table_name = models.TextField()
    user_name = models.TextField(null=True)
    created_at = models.DateTimeField()
    action = models.CharField(max_length=1, choices=ACTION_TYPES)
    row_data = HStoreField(null=True)
    changed_fields = HStoreField(null=True)

    objects = LoggedActionQuerySet.as_manager()

    class Meta:
        managed = False
        db_table = "audit_logged_actions"
        ordering = ["event_id"]
        verbose_name = _("logged action")
        verbose_name_plural = _("logged actions")

    def __str__(self):
        return "%s %s by %s at %s" % (
            self.get_action_display(),
            self.table_name,
            self.user_name,
            self.created_at,
        )

    @cached_property
    def user_id(self):
        match = re.search(r"^user-([0-9]+)-", self.user_name)
        return int(match.groups()[0]) if match else None
