from datetime import date, timedelta

from django.core.mail import EmailMultiAlternatives
from django.core.management import BaseCommand
from django.template.loader import render_to_string

from workbench.accounts.middleware import set_user_name
from workbench.calendar.models import App, Day, activate_app


def monday(day):
    return day - timedelta(days=day.weekday())


class Command(BaseCommand):
    def handle(self, **options):
        set_user_name("Hangar")
        self.today = date.today()
        self.monday = monday(self.today)

        if self.today == self.monday:
            self.monday_mails()

        self.unhandled_mails()

    def monday_mails(self):
        for app in App.objects.all():
            with activate_app(app.slug):
                weeks = {}
                for day in app.days.filter(
                    day__range=[self.monday, self.monday + timedelta(days=13)]
                ).select_related("handled_by"):
                    weeks.setdefault(monday(day.day), []).append(day)

                if not weeks:
                    continue

                mail = EmailMultiAlternatives(
                    "Wochenplan: {}".format(app.title),
                    bcc=[user.email for user in app.users.all()],
                )
                mail.attach_alternative(
                    render_to_string(
                        "mails/week.html", {"app": app, "weeks": sorted(weeks.items())}
                    ),
                    "text/html",
                )
                mail.send()

    def unhandled_mails(self):
        per_app = {}
        for day in Day.objects.filter(
            day__range=[self.today, self.monday + timedelta(days=7)], handled_by=None
        ).select_related("app"):
            per_app.setdefault(day.app, []).append(day)

        for app, days in per_app.items():
            with activate_app(app.slug):
                mail = EmailMultiAlternatives(
                    "Nicht besetzte Tage: {}".format(app.title),
                    bcc=[user.email for user in app.users.all()],
                )
                mail.attach_alternative(
                    render_to_string(
                        "mails/unhandled.html",
                        {"app": app, "days": days, "today": self.today},
                    ),
                    "text/html",
                )
                mail.send()
