from django.db import migrations

from workbench.tools import search


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0029_alter_internaltype_ordering"),
        ("awt", "0004_auto_20190327_0945"),
        ("contacts", "0006_auto_20190321_1445"),
        ("credit_control", "0003_auto_20190321_1447"),
        ("deals", "0002_auto_20200219_1234"),
        ("invoices", "0012_invoice__fts"),
        ("logbook", "0006_auto_20190321_1448"),
        ("offers", "0010_offer__fts"),
    ]

    operations = [
        migrations.RunSQL(search.fts("awt_absence", ["description"])),
        migrations.RunSQL("UPDATE awt_absence SET id=id"),
        migrations.RunSQL(search.fts("contacts_organization", ["name"])),
        migrations.RunSQL(
            search.fts(
                "contacts_person", ["given_name", "family_name", "address", "notes"]
            )
        ),
        migrations.RunSQL("update contacts_organization set id=id"),
        migrations.RunSQL("update contacts_person set id=id"),
        migrations.RunSQL(
            search.fts(
                "credit_control_creditentry",
                ["reference_number", "total", "payment_notice", "notes"],
            )
        ),
        migrations.RunSQL("update credit_control_creditentry set id=id"),
        migrations.RunSQL(
            search.fts(
                "deals_deal",
                ["title", "description", "closing_notice", "_fts"],
            )
        ),
        migrations.RunSQL("update deals_deal set id=id"),
        migrations.RunSQL(
            search.fts(
                "invoices_recurringinvoice", ["title", "description", "postal_address"]
            )
        ),
        migrations.RunSQL(
            search.fts(
                "invoices_invoice", ["title", "description", "postal_address", "_fts"]
            )
        ),
        migrations.RunSQL("update invoices_recurringinvoice set id=id"),
        migrations.RunSQL("update invoices_invoice set id=id"),
        migrations.RunSQL(search.fts("logbook_loggedcost", ["description"])),
        migrations.RunSQL(search.fts("logbook_loggedhours", ["description"])),
        migrations.RunSQL("update logbook_loggedcost set id=id"),
        migrations.RunSQL("update logbook_loggedhours set id=id"),
        migrations.RunSQL(
            search.fts(
                "offers_offer", ["title", "description", "postal_address", "_fts"]
            )
        ),
        migrations.RunSQL("update offers_offer set id=id"),
        migrations.RunSQL(
            search.fts("projects_project", ["title", "description", "_fts"])
        ),
        migrations.RunSQL("update projects_project set id=id"),
        migrations.RunSQL(search.fts("projects_service", ["title", "description"])),
        migrations.RunSQL("update projects_service set id=id"),
        migrations.RunSQL(
            search.fts("projects_campaign", ["title", "description", "_fts"])
        ),
        migrations.RunSQL("update projects_campaign set id=id"),
    ]
