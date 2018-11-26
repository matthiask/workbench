from datetime import timedelta

from django.core.signing import Signer
from django.http import HttpResponse

from icalendar import Calendar, Event

from .models import Day


def ics(request, code):
    email = Signer(salt="ics").unsign(code)

    cal = Calendar()
    cal.add("prodid", "//Bruchpiloten//Hangar//")
    cal.add("version", "2.0")

    for day in Day.objects.filter(handled_by__email=email).select_related("app"):
        event = Event()
        event.add("summary", day.app.title)
        event.add("dtstamp", day.day)
        event.add("dtstart", day.day)
        event.add("dtend", day.day + timedelta(days=1))
        event.add("uid", "bruchpiloten-hangar-{}".format(day.pk))
        cal.add_component(event)

    response = HttpResponse(cal.to_ical(), content_type="text/calendar")
    response["filename"] = "hangar.ics"
    response["content-disposition"] = 'inline; filename="hangar.ics"'
    return response
