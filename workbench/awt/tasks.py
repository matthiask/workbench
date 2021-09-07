import datetime as dt

from django.conf import settings

from authlib.email import render_to_mail

from workbench.awt.reporting import annual_working_time_warnings


def annual_working_time_warnings_mails():
    if dt.date.today().day != 7 or settings.WORKBENCH.SSO_DOMAIN != "feinheit.ch":
        return

    stats = annual_working_time_warnings()
    if not stats["warnings"]:
        return

    render_to_mail(
        "awt/awt_warning_mail",
        {"stats": stats, "WORKBENCH": settings.WORKBENCH},
        to=["partner@feinheit.ch"],
        cc=["workbench@feinheit.ch"],
    ).send()

    for user, running_sum in stats["warnings"]:
        render_to_mail(
            "awt/individual_awt_warning_mail",
            {
                "user": user,
                "running_sum": running_sum,
                "month": stats["month"],
                "WORKBENCH": settings.WORKBENCH,
            },
            to=[user.email],
            cc=["workbench@feinheit.ch"],
        ).send()
