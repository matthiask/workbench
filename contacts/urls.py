from django.conf.urls import patterns, url
from django.shortcuts import redirect

from contacts import views


urlpatterns = patterns(
    '',
    url(
        r'^$',
        lambda request: redirect('contacts_organization_list'),
        name='contacts'),
    url(
        r'^organizations/$',
        views.OrganizationListView.as_view(),
        name='contacts_organization_list'),
    url(
        r'^organizations/(?P<pk>\d+)/$',
        views.OrganizationDetailView.as_view(),
        name='contacts_organization_detail'),
    url(
        r'^organizations/create/$',
        views.OrganizationCreateView.as_view(),
        name='contacts_organization_create'),
    url(
        r'^organizations/(?P<pk>\d+)/update/$',
        views.OrganizationUpdateView.as_view(),
        name='contacts_organization_update'),

    url(
        r'^people/$',
        views.PersonListView.as_view(),
        name='contacts_person_list'),
    url(
        r'^people/(?P<pk>\d+)/$',
        views.PersonDetailView.as_view(),
        name='contacts_person_detail'),
    url(
        r'^people/create/$',
        views.PersonCreateView.as_view(),
        name='contacts_person_create'),
    url(
        r'^people/(?P<pk>\d+)/update/$',
        views.PersonUpdateView.as_view(),
        name='contacts_person_update'),
)
