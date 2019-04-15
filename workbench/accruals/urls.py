from django.conf.urls import url

from workbench import generic
from workbench.accruals.forms import CutoffDateForm
from workbench.accruals.models import CutoffDate
from workbench.accruals.views import CutoffDateDetailView


urlpatterns = [
    url(
        r"^$",
        generic.ListView.as_view(model=CutoffDate),
        name="accruals_cutoffdate_list",
    ),
    url(
        r"^(?P<pk>\d+)/$",
        CutoffDateDetailView.as_view(model=CutoffDate),
        name="accruals_cutoffdate_detail",
    ),
    url(
        r"^create/$",
        generic.CreateView.as_view(model=CutoffDate, form_class=CutoffDateForm),
        name="accruals_cutoffdate_create",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(model=CutoffDate, form_class=CutoffDateForm),
        name="accruals_cutoffdate_update",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(model=CutoffDate),
        name="accruals_cutoffdate_delete",
    ),
]
