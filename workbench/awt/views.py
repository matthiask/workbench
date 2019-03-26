from datetime import date

from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from workbench import generic
from workbench.accounts.models import User
from workbench.awt.models import Year
from workbench.reporting.annual_working_time import annual_working_time


class ReportView(generic.DetailView):
    model = Year

    def get_object(self):
        self.year = self.request.GET.get("year", date.today().year)
        return self.model._default_manager.filter(year=self.year).first()

    def get(self, request, *args, **kwargs):
        if not self.object:
            messages.error(
                request, _("Annual working time for %s not found.") % self.year
            )
            return redirect("/")
        return self.render_to_response(self.get_context_data())

    def get_context_data(self, **kwargs):
        param = self.request.GET.get("user")
        users = None
        if param == "active":
            users = self.object.active_users()
        elif param:
            users = User.objects.filter(id=param)
        if not users:
            users = [self.request.user]
        return super().get_context_data(
            statistics=annual_working_time(self.object, users=users),
            years=Year.objects.all(),
            **kwargs
        )
