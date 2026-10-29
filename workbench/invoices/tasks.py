import datetime as dt
from collections import defaultdict

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.translation import gettext as _

from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.credit_control.models import CreditEntry
from workbench.invoices.models import Invoice, RecurringInvoice
from workbench.invoices.utils import next_valid_day
from workbench.reporting.key_data import unsent_projected_invoices
from workbench.reporting.squeeze import third_party_costs_components
from workbench.reporting.utils import sum_by
from workbench.tools.formats import Z2, currency, local_date_format


TEMPLATE = """\
{base_url}{recurring_url} ==>
{customer}
{invoiced_on}
{invoice}
{total}
{base_url}{invoice_url}

"""


def create_recurring_invoices_and_notify():
    by_owner = defaultdict(list)
    for ri in RecurringInvoice.objects.renewal_candidates():
        for invoice in ri.create_invoices():
            by_owner[invoice.owned_by].append((ri, invoice))

    for owner, invoices in by_owner.items():
        body = "\n".join(
            TEMPLATE.format(
                invoice=invoice,
                customer=invoice.contact.name_with_organization
                if invoice.contact
                else invoice.customer,
                total=currency(invoice.total),
                invoiced_on=local_date_format(invoice.invoiced_on),
                base_url=settings.WORKBENCH.URL,
                invoice_url=invoice.get_absolute_url(),
                recurring_url=ri.get_absolute_url(),
            )
            for (ri, invoice) in invoices
        )
        mail = EmailMultiAlternatives(
            _("recurring invoices"),
            body,
            to=[owner.email],
            cc=settings.RECURRING_INVOICES_CC,
            reply_to=[owner.email],
        )
        mail.send()


PROJECTED_GROSS_MARGIN_TEMPLATE = """\
{project}
{base_url}{project_url}
Geplanter bereinigter Umsatz bis {eom}: {projected}
Verrechnet exkl. MwSt.: {invoiced}
Fremdkosten: {costs} (auf Rechnungen: {invoiced_costs}, erfasst: {logged_costs})
Verrechneter bereinigter Umsatz: {gross_margin}
Delta: {unsent}
"""


def send_unsent_projected_invoices_reminders():
    today = dt.date.today()
    next_month = next_valid_day(today.year, today.month, 99)
    if (next_month - today).days != 3:  # third-last day of month
        return

    upi = list(unsent_projected_invoices(next_month))
    project_ids = [project["project"].id for project in upi]
    invoiced = sum_by(
        Invoice.objects.invoiced().filter(project__in=project_ids), key="project"
    )
    invoiced_costs, logged_costs = third_party_costs_components(project_ids)
    eom = local_date_format(next_month - dt.timedelta(days=1))
    by_user = defaultdict(list)

    for project in upi:
        by_user[project["project"].owned_by].append(project)

    for user, projects in by_user.items():
        body = "\n\n".join(
            PROJECTED_GROSS_MARGIN_TEMPLATE.format(
                project=project["project"],
                base_url=settings.WORKBENCH.URL,
                project_url=project["project"].get_absolute_url(),
                eom=eom,
                projected=currency(
                    sum(
                        (
                            pi.gross_margin
                            for pi in project["projected"]
                            if pi.invoiced_on < next_month
                        ),
                        Z2,
                    )
                ),
                invoiced=currency(invoiced[project["project"].id]),
                costs=currency(
                    invoiced[project["project"].id] - project["gross_margin"]
                ),
                invoiced_costs=currency(invoiced_costs[project["project"].id]),
                logged_costs=currency(logged_costs[project["project"].id]),
                gross_margin=currency(project["gross_margin"]),
                unsent=currency(project["unsent"]),
            )
            for project in projects
        )
        EmailMultiAlternatives(
            "{} ({})".format(_("Unsent projected invoices"), eom),
            f"""\
Hallo {user}

Der geplante bereinigte Umsatz per {eom} wurde bei
folgenden Projekten noch nicht erreicht:

{body}

Der bereinigte Umsatz ist das Rechnungstotal exkl. MwSt. abzüglich der
Fremdkosten. Als Fremdkosten zählt der grössere Betrag: die Fremdkosten
auf den Rechnungen oder die erfassten Fremdkosten. Erfasste Fremdkosten,
welche noch nicht weiterverrechnet wurden, verringern deshalb den
verrechneten bereinigten Umsatz.

Wenn Du die Rechnungen nicht stellen kannst, aktualisiere bitte
die geplanten Rechnungen oder schliesse das Projekt.
""",
            to=[user.email],
            reply_to=[user.email],
        ).send()


def autodunning():
    managers = [
        user.email
        for user in User.objects.active()
        if user.features[FEATURES.AUTODUNNING]
    ]
    if not managers:
        return

    try:
        latest = CreditEntry.objects.latest("value_date").value_date
    except CreditEntry.DoesNotExist:
        latest = dt.date.min

    if (dt.date.today() - latest).days > 3:
        EmailMultiAlternatives(
            _("Auto dunning"),
            _(
                "Please update the list of credit entries. Generating dunning letters doesn't make sense without up-to-date payment information."
            ),
            to=managers,
            reply_to=managers,
        ).send()
        return

    invoices = (
        Invoice.objects
        .autodunning()
        .select_related("customer", "contact__organization", "owned_by", "project")
        .order_by("customer", "contact")
    )

    if not invoices:
        EmailMultiAlternatives(
            _("Auto dunning"),
            _("No overdue invoices with missing recent reminders."),
            to=managers,
            reply_to=managers,
        ).send()
        return

    contacts = {}
    for invoice in invoices:
        contacts.setdefault(invoice.contact, []).append(invoice)
    contact_details = "\n\n".join(
        f"{contact.organization}\n{contact}\n{currency(sum(invoice.total_excl_tax for invoice in contact_invoices))}"
        for contact, contact_invoices in contacts.items()
    )
    cc = list({
        invoice.owned_by.email for invoice in invoices if invoice.owned_by.is_active
    })

    mail = EmailMultiAlternatives(
        _("Auto dunning"),
        "\n".join((
            "{}: {}".format(
                _("Responsible"),
                ", ".join(managers),
            ),
            "{}: {}".format(
                _("For your information"),
                ", ".join(cc),
            ),
            "",
            contact_details,
        )),
        to=managers,
        cc=cc,
        reply_to=managers,
    )
    mail.send()


def tuesday_autodunning():
    today = dt.date.today()
    if today.weekday() != 1:
        return
    autodunning()
