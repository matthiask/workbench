from django.conf.urls import url

from workbench import generic
from workbench.accruals.forms import AccrualForm, AccrualSearchForm
from workbench.accruals.models import Accrual


urlpatterns = [
    url(
        r"^$",
        generic.ListView.as_view(
            model=Accrual,
            search_form_class=AccrualSearchForm,
            # show_create_button=False,
        ),
        name="accruals_accrual_list",
    ),
    url(
        r"^(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=Accrual),
        name="accruals_accrual_detail",
    ),
    url(
        r"^create/$",
        generic.CreateView.as_view(model=Accrual, form_class=AccrualForm),
        name="accruals_accrual_create",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(model=Accrual, form_class=AccrualForm),
        name="accruals_accrual_update",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(model=Accrual),
        name="accruals_accrual_delete",
    ),
]
