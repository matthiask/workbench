from django.contrib.postgres.fields import HStoreField
from django.db import connections, models

from psycopg2.extras import register_hstore


class LoggedActionManager(models.Manager):
    def register_hstore(self):
        register_hstore(
            connections['default'].cursor(),
            globally=True)

    def get_queryset(self, *args, **kwargs):
        self.register_hstore()
        return super().get_queryset(*args, **kwargs)

    def for_instance(self, instance):
        return self.filter(
            table_name=instance._meta.db_table,
            object_id=instance.id,
        )


class LoggedAction(models.Model):
    ACTION_TYPES = (
        ('I', 'INSERT'),
        ('U', 'UPDATE'),
        ('D', 'DELETE'),
        ('T', 'TRUNCATE'),
    )

    event_id = models.IntegerField(primary_key=True)
    table_name = models.TextField()
    user_name = models.TextField(null=True)
    created_at = models.DateTimeField()
    action = models.CharField(max_length=1, choices=ACTION_TYPES)
    row_data = HStoreField(null=True)
    changed_fields = HStoreField(null=True)

    objects = LoggedActionManager()

    class Meta:
        managed = False
        db_table = 'audit_logged_actions'
        ordering = ('created_at',)

    def __str__(self):
        return '%s %s at %s' % (
            self.get_action_display(),
            self.table_name,
            self.created_at,
        )
