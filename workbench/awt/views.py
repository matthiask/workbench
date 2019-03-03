from datetime import date

from django.shortcuts import get_object_or_404

from workbench.accounts.models import User
from workbench.awt.models import Year
from workbench import generic


class ReportView(generic.DetailView):
    def get_object(self):
        return get_object_or_404(
            Year, year=self.request.GET.get("year", date.today().year)
        )

    def get_context_data(self, **kwargs):
        param = self.request.GET.get("user")
        users = None
        if param == "active":
            users = User.objects.filter(is_active=True)
        elif param:
            users = User.objects.filter(id=param)
        if not users:
            users = [self.request.user]
        return super().get_context_data(
            statistics=self.object.statistics(users=users), **kwargs
        )
