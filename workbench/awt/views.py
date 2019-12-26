import datetime as dt

from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from workbench import generic
from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.awt.models import Year
from workbench.awt.reporting import annual_working_time


class ReportView(generic.DetailView):
    model = Year

    def get_object(self):
        self.year = int(self.request.GET.get("year", dt.date.today().year))
        return self.model._default_manager.filter(year=self.year).first()

    def get(self, request, *args, **kwargs):
        if not self.object:
            messages.error(request, _("Target time for %s not found.") % self.year)
            return redirect("/")
        return self.render_to_response(self.get_context_data())

    def get_context_data(self, **kwargs):
        param = self.request.GET.get("user")
        users = None
        if param == "active" and self.request.user.features[FEATURES.CONTROLLING]:
            users = self.object.active_users()
        elif param and param != "active":
            users = User.objects.filter(id=param)
        if not users:
            users = [self.request.user]
        return super().get_context_data(
            statistics=annual_working_time(self.object.year, users=users),
            year=self.year,
            years=sorted(
                Year.objects.filter(year__lte=dt.date.today().year)
                .order_by()
                .values_list("year", flat=True)
                .distinct(),
                reverse=True,
            ),
            **kwargs
        )
