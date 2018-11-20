from django.conf.urls import url
from django.urls import reverse_lazy

from workbench import generic

from .forms import DayForm
from .models import Day


urlpatterns = [
    url(
        r"^$",
        generic.ListView.as_view(model=Day, paginate_by=None),
        name="cooking_day_list",
    ),
    url(
        r"^(?P<pk>[0-9]+)/$",
        generic.DetailView.as_view(model=Day),
        name="cooking_day_detail",
    ),
    url(
        r"^create/$",
        generic.CreateView.as_view(model=Day, form_class=DayForm),
        name="cooking_day_create",
    ),
    url(
        r"^(?P<pk>[0-9]+)/update/$",
        generic.UpdateView.as_view(
            model=Day, form_class=DayForm, success_url=reverse_lazy("cooking_day_list")
        ),
        name="cooking_day_update",
    ),
    url(
        r"^(?P<pk>[0-9]+)/delete/$",
        generic.DeleteView.as_view(model=Day),
        name="cooking_day_delete",
    ),
]
