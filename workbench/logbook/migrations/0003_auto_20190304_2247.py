# Generated by Django 2.1.7 on 2019-03-04 21:47

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("logbook", "0002_auto_20190304_2239"), ("audit", "0001_initial")]

    operations = [
        migrations.RunSQL("SELECT audit_audit_table('logbook_loggedhours');"),
        migrations.RunSQL("SELECT audit_audit_table('logbook_loggedcost');"),
    ]
