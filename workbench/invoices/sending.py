"""Sending invoices to customers by mail, from the invoice (SendInvoiceForm)
or automatically from recurring invoices"""

import datetime as dt
import io

from authlib.email import render_to_mail
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils.translation import gettext as _, override

from workbench.invoices.models import Invoice
from workbench.reporting.models import FreezeDate
from workbench.tools.formats import currency, local_date_format
from workbench.tools.pdf import PDFDocument, invoice_filename


def contact_emails(invoice):
    return (
        list(invoice.contact.emailaddresses.values_list("email", flat=True))
        if invoice.contact
        else []
    )


def suggested_emails(invoice):
    """The accounts payable address of the organization, the contact's
    addresses and the central address of the organization, like the payment
    reminders"""
    organization = (
        invoice.contact.organization if invoice.contact else None
    ) or invoice.customer
    return list(
        dict.fromkeys(
            filter(
                None,
                [
                    organization.accounts_payable_email,
                    *contact_emails(invoice),
                    organization.email,
                ],
            )
        )
    )


def address(invoice, email):
    """The contact's salutation and Du or Sie only for their own addresses"""
    contact = invoice.contact
    personal = bool(contact and email in contact_emails(invoice))
    first_name_terms = personal and contact.address_on_first_name_terms
    return {
        # Old contacts may lack a salutation
        "salutation": (personal and contact.salutation)
        or (
            f"Hallo {contact.given_name}"
            if first_name_terms
            else "Sehr geehrte Damen und Herren"
        ),
        "first_name_terms": first_name_terms,
    }


def fill(text, invoice):
    """Replaces the placeholders with the values of the invoice"""
    for placeholder, value in [
        ("{code}", invoice.code),
        ("{total}", currency(invoice.total)),
        ("{due_on}", local_date_format(invoice.due_on)),
        ("{service_period}", invoice.service_period or ""),
    ]:
        text = text.replace(placeholder, value)
    return text


def proposal(obj, email, *, code=None, total=None):
    """The proposed subject and text of the mail to ``email`` for an invoice
    or a recurring invoice (with placeholders for the values of each
    invoice); the text contains the placeholder {due_on}"""
    mail = render_to_mail(
        "invoices/invoice_mail",
        {
            "code": code or obj.code,
            "title": obj.title,
            "total": total or currency(obj.total),
            "owner": obj.owned_by,
            **address(obj, email),
            "WORKBENCH": settings.WORKBENCH,
        },
    )
    return mail.subject, mail.body


def recurring_proposal(recurring_invoice, email):
    return proposal(recurring_invoice, email, code="{code}", total="{total}")


def invoice_mail(invoice, *, to, subject, body):
    """The mail with the PDF to ``to``, the owner in Cc and Reply-To"""
    owner = [invoice.owned_by.email] if invoice.owned_by.is_active else []
    mail = EmailMultiAlternatives(
        fill(subject, invoice),
        fill("\n".join(body.splitlines()), invoice),
        from_email=settings.WORKBENCH.REMINDER_FROM_EMAIL,
        to=[to],
        cc=owner,
        reply_to=owner,
        bcc=[
            email
            for email in [settings.WORKBENCH.REMINDER_FROM_EMAIL]
            if email and email not in owner
        ],
    )
    with io.BytesIO() as buf, override(settings.WORKBENCH.PDF_LANGUAGE):
        pdf = PDFDocument(buf)
        pdf.init_invoice_letter()
        pdf.process_invoice(invoice)
        pdf.generate()
        mail.attach(
            f"{invoice_filename(invoice)}.pdf", buf.getvalue(), "application/pdf"
        )
    return mail


def send(invoice, *, to, subject, body, save=None):
    """Marks the invoice as sent and mails it; it stays in preparation if the
    mail can't be sent (exceptions are raised)"""
    invoice.status = Invoice.SENT
    try:
        with transaction.atomic():
            (save or invoice.save)()
            invoice_mail(invoice, to=to, subject=subject, body=body).send()
    except Exception:
        invoice.status = Invoice.IN_PREPARATION
        raise


def send_automatically(invoice, recurring_invoice):
    """Sends a new invoice of a recurring invoice with its recipient, subject
    and text (or the proposal); invoice dates on or before the freeze date
    move to the day after it (the due date too). ``invoice.sending`` says
    what happened"""
    emails = suggested_emails(invoice)
    if not (to := recurring_invoice.send_to or (emails[0] if emails else "")):
        invoice.sending = _("Not sent: %s") % _("No email address.")
        return
    if invoice.invoiced_on <= (freeze := FreezeDate.objects.up_to()):
        days = invoice.due_on - invoice.invoiced_on
        invoice.invoiced_on = freeze + dt.timedelta(days=1)
        invoice.due_on = invoice.invoiced_on + days
    subject, body = proposal(invoice, to)
    try:
        send(
            invoice,
            to=to,
            subject=recurring_invoice.mail_subject or subject,
            body=recurring_invoice.mail_body or body,
        )
    except Exception as exc:  # noqa: BLE001
        invoice.sending = _("Not sent: %s") % exc
    else:
        invoice.sending = _("Sent to %s") % to
