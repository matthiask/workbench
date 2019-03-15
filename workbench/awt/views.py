from datetime import date

from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from workbench.accounts.models import User
from workbench.awt.models import Employment, Year
from workbench.reporting.annual_working_time import annual_working_time
from workbench import generic


class ReportView(generic.DetailView):
    model = Year

    def get(self, request, *args, **kwargs):
        year = request.GET.get("year", date.today().year)
        try:
            self.object = Year.objects.get(year=year)
        except Year.DoesNotExist:
            messages.error(request, _("Annual working time for %s not found.") % year)
            return redirect("/")
        return self.render_to_response(self.get_context_data())

    def get_context_data(self, **kwargs):
        param = self.request.GET.get("user")
        users = None
        if param == "active":
            users = User.objects.filter(
                id__in=Employment.objects.filter(
                    date_from__lte=date(self.object.year, 12, 31),
                    date_until__gte=date(self.object.year, 1, 1),
                ).values("user")
            )
        elif param:
            users = User.objects.filter(id=param)
        if not users:
            users = [self.request.user]
        return super().get_context_data(
            statistics=annual_working_time(self.object, users=users), **kwargs
        )
