from workbench.audit.models import LoggedAction
from workbench.tools.validation import in_days


def prune_audit():
    """Data is pruned after a while to keep the audit log small and for data
    protection. Users, employments and the configuration stay; revisit
    anonymizing users after about ten years."""
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
            "awt_holiday",
            "planning_milestone",
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
            "invoices_service",
            "credit_control_creditentry",
            "expenses_expensereport",
            "projects_budgettransfer",
            "projects_campaign",
            "notes_note",
        ],
        created_at__lt=in_days(-5 * 366),
    ).delete()
