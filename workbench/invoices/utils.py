# Copied 1:1 from django-user-payments

import itertools
from datetime import date, timedelta


def next_valid_day(year, month, day):
    """
    Return the next valid date for the given year, month and day combination.

    Used by ``recurring`` below.
    """
    while True:
        try:
            return date(year, month, day)
        except ValueError:
            if month > 12:
                month -= 12
                year += 1
                continue

            day += 1
            if day > 31:
                day = 1
                month += 1


def recurring(start, periodicity):
    """
    This generator yields valid dates with the given start date and
    periodicity.

    Returns later dates if calculated dates do not exist, e.g. for a yearly
    periodicity and a starting date of 2016-02-29 (a leap year), dates for
    years that aren't leap years will be 20xx-03-01, not 20xx-02-28. However,
    leap year dates will stay on 20xx-02-29 and not be delayed.
    """
    if periodicity == "yearly":
        return (  # pragma: no branch
            next_valid_day(start.year + i, start.month, start.day)
            for i in itertools.count()
        )

    elif periodicity == "quarterly":
        return (  # pragma: no branch
            next_valid_day(start.year, start.month + i * 3, start.day)
            for i in itertools.count()
        )

    elif periodicity == "monthly":
        return (  # pragma: no branch
            next_valid_day(start.year, start.month + i, start.day)
            for i in itertools.count()
        )

    elif periodicity == "weekly":
        return (  # pragma: no branch
            start + timedelta(days=i * 7) for i in itertools.count()
        )

    else:
        raise ValueError("Unknown periodicity %r" % periodicity)


if __name__ == "__main__":  # pragma: no cover
    from pprint import pprint

    def twenty(start, periodicity):
        pprint(list(itertools.islice(recurring(start, periodicity), 20)))
        print()

    twenty(date.today(), "yearly")
    twenty(date(2016, 2, 29), "yearly")

    twenty(date.today(), "monthly")
    twenty(date(2016, 2, 29), "monthly")
    twenty(date(2015, 7, 31), "monthly")

    twenty(date.today(), "weekly")
