import csv
import datetime as dt
import hashlib
import io
import re
from decimal import Decimal

from django.utils.dateparse import parse_date
from django.utils.encoding import force_str
from django.utils.text import slugify


def parse_zkb_csv(data):
    f = io.StringIO()
    f.write(force_str(data, encoding="utf-8", errors="ignore"))
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
            day = dt.datetime.strptime(row[8], "%d.%m.%Y").date()
            amount = row[7] and Decimal(row[7])
            reference = row[4]
        except (AttributeError, IndexError, ValueError):
            continue
        if day and amount:
            details = next(reader)
            entries.append(
                {
                    "reference_number": reference,
                    "value_date": day,
                    "total": amount,
                    "payment_notice": "; ".join(
                        filter(None, (details[1], details[10], row[4]))
                    ),
                }
            )
    return entries


def postfinance_preprocess_notice(payment_notice):
    """Remove spaces from potential invoice numbers"""
    return re.sub(
        r"\b([0-9]{4}\s*-\s*[0-9]{4}\s*-\s*[0-9]{4})\b",
        lambda match: re.sub(r"\s+", "", match.group(0)),
        payment_notice,
    )


def postfinance_reference_number(payment_notice, day):
    """Either pull out the bank reference or create a hash from the notice"""
    match = re.search(r"\b([0-9]{6}[A-Z]{2}[0-9A-Z]{6,10})$", payment_notice)
    return "pf-{}".format(
        match.group(1)
        if match
        else hashlib.md5(
            slugify(payment_notice + day.isoformat()).encode("utf-8")
        ).hexdigest()
    )


def parse_postfinance_csv(data):
    f = io.StringIO()
    f.write(force_str(data, encoding="latin-1", errors="ignore"))
    f.seek(0)
    dialect = csv.Sniffer().sniff(f.read(4096))
    f.seek(0)
    reader = csv.reader(f, dialect)
    next(reader)  # Skip first line
    entries = []
    for row in reader:
        if not row:
            continue
        try:
            day = parse_date(row[4])
        except (IndexError, ValueError):
            continue
        if day is None or not row[2]:  # Only credit
            continue

        payment_notice = postfinance_preprocess_notice(row[1])
        entries.append(
            {
                "reference_number": postfinance_reference_number(payment_notice, day),
                "value_date": day,
                "total": Decimal(row[2]),
                "payment_notice": payment_notice,
            }
        )
    return entries
