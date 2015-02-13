from django.conf.urls import patterns, url

from contacts import views


urlpatterns = patterns(
    '',
    url(
        r'^organizations/$',
        views.OrganizationListView.as_view(),
        name='contacts_organization_list'),
    url(
        r'^organizations/(?P<pk>\d+)/$',
        views.OrganizationDetailView.as_view(),
        name='contacts_organization_detail'),

    url(
        r'^people/$',
        views.PersonListView.as_view(),
        name='contacts_person_list'),
    url(
        r'^people/(?P<pk>\d+)/$',
        views.PersonDetailView.as_view(),
        name='contacts_person_detail'),
)
