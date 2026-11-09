import datetime as dt

from workbench.accounts.models import User
from workbench.tools.reporting import query


# Dates this long ago are still shown, everything else comes up within a year
RECENTLY = dt.timedelta(days=60)


def _on(day, year):
    """The yearly date in the given year, February 29 is February 28 otherwise"""
    try:
        return day.replace(year=year)
    except ValueError:
        return day.replace(year=year, day=28)


def _occurrence(day, today):
    """The yearly date if it was recently, otherwise the next one"""
    latest = _on(day, today.year)
    if latest > today:
        latest = _on(day, today.year - 1)
    return latest if today - latest <= RECENTLY else _on(day, latest.year + 1)


def work_anniversaries():
    anniversaries = []
    today = dt.date.today()

    for user in User.objects.active():
        if user.date_of_employment:
            # The first day of work until the first anniversary
            on = max(
                _occurrence(user.date_of_employment, today), user.date_of_employment
            )
            anniversaries.append({
                "user": user,
                "this_year": on,
                "anniversary": on.year - user.date_of_employment.year,
                "already": on < today,
            })
        else:
            anniversaries.append({
                "user": user,
                "this_year": dt.date.max,
                "already": False,
            })

    return sorted(
        anniversaries, key=lambda row: (row["this_year"], row["user"].get_full_name())
    )


def birthdays():
    users_with_birthdays, users_without_birthdays = [], []
    today = dt.date.today()
    for user in User.objects.active().select_related("person"):
        if user.person and (dob := user.person.date_of_birth):
            on = _occurrence(dob, today)
            users_with_birthdays.append({
                "user": user,
                "on": on,
                "already": on < today,
                "age": on.year - dob.year,
            })
        else:
            users_without_birthdays.append(user)

    return {
        "users_with_birthdays": sorted(
            users_with_birthdays,
            key=lambda row: (row["on"], row["user"].get_full_name()),
        ),
        "users_without_birthdays": users_without_birthdays,
    }


def average_employment_duration():
    stats = {}

    stats["current_users"] = query(
        """
with date_from_until as (
    select
        user_id,
        date_from,
        -- Only the past part of employments counts
        least(date_until, current_date) as date_until
    from awt_employment e
    left join accounts_user u on e.user_id=u.id
    where u.is_active=TRUE and date_from <= current_date
),
durations as (
select user_id, sum(date_until - date_from) as duration
from date_from_until
group by user_id
)
select avg(duration)/365.24 from durations
        """,
        [],
    )[0][0]

    stats["all_users"] = query(
        """
with date_from_until as (
    select
        user_id,
        date_from,
        -- Only the past part of employments counts
        least(date_until, current_date) as date_until
    from awt_employment
    where date_from <= current_date
),
durations as (
select user_id, sum(date_until - date_from) as duration
from date_from_until
group by user_id
)
select avg(duration)/365.24 from durations
        """,
        [],
    )[0][0]

    return stats


def test():  # pragma: no cover
    from pprint import pprint

    pprint(work_anniversaries())
