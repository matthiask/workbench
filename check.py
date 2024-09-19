import csv
import datetime as dt
from decimal import Decimal
from pprint import pprint

from workbench.invoices.models import Invoice


def check():
    with open("/home/matthias/Downloads/transformed.csv", encoding="utf-8") as f:
        # data = list(csv.reader(f))[407:613]
        data = list(csv.reader(f))

    # print(data)
    invoices = {row[2][1:]: Decimal(row[1]) for row in data}
    pprint(invoices)

    missing = 0
    open_items = 0

    for invoice in Invoice.objects.invoiced().filter(
        invoiced_on__range=[dt.date(2023, 1, 1), dt.date(2023, 12, 31)],
    ):
        if invoice.code not in invoices:
            if not invoice.closed_on:
                open_items += invoice.total_excl_tax
            elif invoice.closed_on and invoice.closed_on > dt.date(2023, 12, 31):
                pass
                # print(f"Invoice paid later {invoice}")
            else:
                print(f"Invoice missing: {invoice} {invoice.total_excl_tax}")
                missing += invoice.total_excl_tax
        elif invoices[invoice.code] != invoice.total:
            print(
                f"Different total: {invoice} {invoices[invoice.code]} != {invoice.total}"
            )

    print(f"Missing total excl. tax: {missing}")
    print(f"Open items: {open_items}")
