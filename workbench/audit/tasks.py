from workbench.audit.models import LoggedAction
from workbench.tools.validation import in_days


def prune_audit():
    LoggedAction.objects.filter(
        table_name__in=[
            "accounts_specialistfield",
            "accounts_team",
            "logbook_break",
            "logbook_loggedcost",
            "logbook_loggedhours",
        ],
        created_at__lt=in_days(-2 * 366),
    ).delete()

    LoggedAction.objects.filter(
        table_name__in=[
            "awt_absence",
            "invoices_projectedinvoice",
            "deals_value",
            "deals_deal",
            "deals_contribution",
            "planning_milestone",
            "planning_publicholiday",
            "planning_plannedwork",
        ],
        created_at__lt=in_days(-3 * 366),
    ).delete()

    LoggedAction.objects.filter(
        table_name__in=[
            "contacts_organization",
            "contacts_person",
            "contacts_phonenumber",
            "contacts_emailaddress",
            "contacts_postaladdress",
            "projects_service",
            "projects_project",
            "offers_offer",
            "invoices_recurringinvoice",
            "invoices_invoice",
        ],
        created_at__lt=in_days(-5 * 366),
    ).delete()
