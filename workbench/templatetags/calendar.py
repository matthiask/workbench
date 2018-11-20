from django import template


register = template.Library()


@register.filter
def calendar(days):
    if not days:
        return

    week = [None] * 5
    key = days[0].day.isocalendar()[:2]
    previous = days[0].day
    for day in days:
        if day.day.isocalendar()[:2] != key:
            key = day.day.isocalendar()[:2]
            yield previous, week[:]
            week[:] = [None] * 5
        week[day.day.weekday()] = day
        previous = day.day
    yield previous, week[:]
