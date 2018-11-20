from django.conf.urls import url

from activities.forms import ActivitySearchForm, ActivityForm
from activities.models import Activity
from tools.views import ListView, DetailView, CreateView, UpdateView, DeleteView


urlpatterns = [
    url(
        r"^$",
        ListView.as_view(model=Activity, search_form_class=ActivitySearchForm),
        name="activities_activity_list",
    ),
    url(
        r"^(?P<pk>\d+)/$",
        DetailView.as_view(model=Activity),
        name="activities_activity_detail",
    ),
    url(
        r"^create/$",
        CreateView.as_view(
            model=Activity, form_class=ActivityForm, template_name="modalform.html"
        ),
        name="activities_activity_create",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        UpdateView.as_view(
            model=Activity, form_class=ActivityForm, template_name="modalform.html"
        ),
        name="activities_activity_update",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        DeleteView.as_view(model=Activity),
        name="activities_activity_delete",
    ),
]
