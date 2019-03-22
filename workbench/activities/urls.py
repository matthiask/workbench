from django.conf.urls import url

from workbench import generic
from workbench.activities.forms import ActivitySearchForm, ActivityForm
from workbench.activities.models import Activity


urlpatterns = [
    url(
        r"^$",
        generic.ListView.as_view(model=Activity, search_form_class=ActivitySearchForm),
        name="activities_activity_list",
    ),
    url(
        r"^(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=Activity),
        name="activities_activity_detail",
    ),
    url(
        r"^create/$",
        generic.CreateView.as_view(
            model=Activity, form_class=ActivityForm, template_name="modalform.html"
        ),
        name="activities_activity_create",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(
            model=Activity, form_class=ActivityForm, template_name="modalform.html"
        ),
        name="activities_activity_update",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(model=Activity),
        name="activities_activity_delete",
    ),
]
