import datetime as dt
import io
from collections import defaultdict

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.text import slugify
from django.utils.translation import gettext as _

from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.credit_control.models import CreditEntry
from workbench.invoices.models import Invoice, RecurringInvoice
from workbench.invoices.utils import next_valid_day
from workbench.reporting.key_data import unsent_projected_invoices
from workbench.tools.formats import currency, local_date_format
from workbench.tools.pdf import PDFDocument


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
        )
        mail.send()


PROJECTED_GROSS_MARGIN_TEMPLATE = """\
{project}
{base_url}{project_url}
Delta: {unsent}
"""


def send_unsent_projected_invoices_reminders():
    today = dt.date.today()
    next_month = next_valid_day(today.year, today.month, 99)
    if (next_month - today).days != 3:  # third-last day of month
        return

    upi = unsent_projected_invoices(next_month)
    by_user = defaultdict(list)

    for project in upi:
        by_user[project["project"].owned_by].append(project)

    for user, projects in by_user.items():
        body = "\n\n".join(
            PROJECTED_GROSS_MARGIN_TEMPLATE.format(
                project=project["project"],
                base_url=settings.WORKBENCH.URL,
                project_url=project["project"].get_absolute_url(),
                unsent=currency(project["unsent"]),
            )
            for project in projects
        )
        eom = local_date_format(next_month - dt.timedelta(days=1))
        EmailMultiAlternatives(
            "{} ({})".format(_("Unsent projected invoices"), eom),
            f"""\
Hallo {user}

Das geplante Rechnungstotal per {eom} wurde bei
folgenden Projekten noch nicht erreicht:

{body}

Wenn Du die Rechnungen nicht stellen kannst, aktualisiere bitte
die geplanten Rechnungen oder schliesse das Projekt.
""",
            to=[user.email],
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
        ).send()
        return

    invoices = (
        Invoice.objects.autodunning()
        .select_related("customer", "contact__organization", "owned_by", "project")
        .order_by("customer", "contact")
    )

    if not invoices:
        EmailMultiAlternatives(
            _("Auto dunning"),
            _("No overdue invoices with missing recent reminders."),
            to=managers,
        ).send()
        return

    contacts = {}
    for invoice in invoices:
        contacts.setdefault(invoice.contact, []).append(invoice)
    contact_details = "\n\n".join(
        f"{contact.organization}\n{contact}\n{currency(sum(invoice.total_excl_tax for invoice in contact_invoices))}"
        for contact, contact_invoices in contacts.items()
    )
    cc = list(
        {invoice.owned_by.email for invoice in invoices if invoice.owned_by.is_active}
    )

    mail = EmailMultiAlternatives(
        _("Auto dunning"),
        "\n".join(
            (
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
            )
        ),
        to=managers,
        cc=cc,
    )
    for contact, contact_invoices in contacts.items():
        with io.BytesIO() as f:
            pdf = PDFDocument(f)
            pdf.dunning_letter(invoices=contact_invoices)
            pdf.generate()
            f.seek(0)
            mail.attach(
                f"reminders-{slugify(contact.name_with_organization)}.pdf",
                f.getvalue(),
                "application/pdf",
            )
    mail.send()
    invoices.update(last_reminded_on=dt.date.today())


def tuesday_autodunning():
    today = dt.date.today()
    if today.weekday() != 1:
        return
    autodunning()
