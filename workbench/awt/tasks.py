import datetime as dt

from django.conf import settings

from authlib.email import render_to_mail

from workbench.awt.reporting import problematic_annual_working_times


def problematic_annual_working_times_mail():
    if dt.date.today().day != 7 or settings.WORKBENCH.SSO_DOMAIN != "feinheit.ch":
        return

    stats = problematic_annual_working_times()
    if not stats["problematic"]:
        return

    render_to_mail(
        "awt/problematic_mail",
        {"stats": stats, "WORKBENCH": settings.WORKBENCH},
        to=["partner@feinheit.ch"],
        cc=["workbench@feinheit.ch"],
    ).send()
