from django.conf.urls import url

from activities.forms import ActivityForm
from activities.models import Activity
from activities.views import ActivityListView
from tools.views import DetailView, CreateView, UpdateView, DeleteView


urlpatterns = [
    url(
        r'^$',
        ActivityListView.as_view(),
        name='activities_activity_list'),
    url(
        r'^(?P<pk>\d+)/$',
        DetailView.as_view(
            model=Activity,
        ),
        name='activities_activity_detail'),
    url(
        r'^create/$',
        CreateView.as_view(
            model=Activity,
            form_class=ActivityForm,
            template_name='modalform.html',
        ),
        name='activities_activity_create'),
    url(
        r'^(?P<pk>\d+)/update/$',
        UpdateView.as_view(
            model=Activity,
            form_class=ActivityForm,
        ),
        name='activities_activity_update'),
    url(
        r'^(?P<pk>\d+)/delete/$',
        DeleteView.as_view(
            model=Activity,
        ),
        name='activities_activity_delete'),
]
