from django.urls import path, re_path

from workbench import generic
from workbench.accounts.forms import TeamForm, TeamSearchForm, UserSearchForm
from workbench.accounts.models import Team, User
from workbench.planning.views import TeamPlanningView, UserPlanningView

from . import views


urlpatterns = [
    re_path(r"^accounts/$", views.accounts, name="accounts"),
    re_path(
        r"^accounts/update/$", views.UserUpdateView.as_view(), name="accounts_update"
    ),
    re_path(r"^accounts/login/$", views.login, name="login"),
    re_path(r"^accounts/oauth2/$", views.oauth2, name="accounts_oauth2"),
    re_path(r"^accounts/logout/$", views.logout, name="logout"),
    #
    path(
        "users/",
        generic.ListView.as_view(
            model=User,
            search_form_class=UserSearchForm,
            show_create_button=False,
        ),
        name="accounts_user_list",
    ),
    path(
        "users/<int:pk>/",
        generic.DetailView.as_view(model=User),
        name="accounts_user_detail",
    ),
    path(
        "users/<int:pk>/planning/",
        UserPlanningView.as_view(),
        name="accounts_user_planning",
    ),
    path(
        "users/<int:pk>/statistics/",
        views.ProfileView.as_view(),
        name="accounts_user_statistics",
    ),
    # Teams
    re_path(
        r"^teams/$",
        generic.ListView.as_view(model=Team, search_form_class=TeamSearchForm),
        name="accounts_team_list",
    ),
    re_path(
        r"^teams/(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=Team),
        name="accounts_team_detail",
    ),
    re_path(
        r"^teams/create/$",
        generic.CreateView.as_view(form_class=TeamForm, model=Team),
        name="accounts_team_create",
    ),
    re_path(
        r"^teams/(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(form_class=TeamForm, model=Team),
        name="accounts_team_update",
    ),
    path(
        "teams/<int:pk>/planning/",
        TeamPlanningView.as_view(),
        name="accounts_team_planning",
    ),
    re_path(
        r"^teams/(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(model=Team),
        name="accounts_team_delete",
    ),
]
