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
            row_data__id=instance.id,
        )


class LoggedAction(models.Model):
    event_id = models.IntegerField(primary_key=True)
    schema_name = models.TextField()
    table_name = models.TextField()
    relid = models.IntegerField()
    session_user_name = models.TextField(null=True)
    action_tstamp_tx = models.DateTimeField()
    action_tstamp_stm = models.DateTimeField()
    transaction_id = models.IntegerField(null=True)
    application_name = models.TextField(null=True)
    client_addr = models.GenericIPAddressField(null=True)
    client_port = models.IntegerField(null=True)
    client_query = models.TextField(null=True)
    action = models.TextField()
    row_data = HStoreField(null=True)
    changed_fields = HStoreField(null=True)
    statement_only = models.BooleanField()

    objects = LoggedActionManager()

    class Meta:
        managed = False
        db_table = 'audit_logged_actions'
        ordering = ('action_tstamp_stm',)
