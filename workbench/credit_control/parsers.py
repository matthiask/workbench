import csv
import io
from datetime import datetime
from decimal import Decimal

from django.utils.encoding import force_text


def parse_zkb(data):
    f = io.StringIO()
    f.write(force_text(data, encoding="utf-8", errors="ignore"))
    f.seek(0)
    dialect = csv.Sniffer().sniff(f.read(4096))
    f.seek(0)
    reader = csv.reader(f, dialect)
    next(reader)  # Skip first line
    entries = []
    while True:
        try:
            row = next(reader)
        except StopIteration:
            break
        if not row:
            continue
        try:
            day = datetime.strptime(row[8], "%d.%m.%Y").date()
            amount = row[7] and Decimal(row[7])
            reference = row[4]
        except (AttributeError, IndexError, ValueError):
            continue
        if day and amount:
            details = next(reader)
            entries.append(
                {
                    "reference_number": reference,
                    "value_date": day.isoformat(),
                    "total": str(amount),
                    "payment_notice": "; ".join(
                        filter(None, (details[1], details[10], row[4]))
                    ),
                }
            )
    return entries
