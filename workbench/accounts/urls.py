from django.urls import path

from workbench import generic
from workbench.accounts import views
from workbench.accounts.forms import TeamForm, TeamSearchForm, UserSearchForm
from workbench.accounts.models import Team, User
from workbench.planning.views import team_planning, user_planning


urlpatterns = [
    path("accounts/", views.accounts, name="accounts"),
    path("accounts/update/", views.UserUpdateView.as_view(), name="accounts_update"),
    path("accounts/login/", views.login, name="login"),
    path("accounts/oauth2/", views.oauth2, name="accounts_oauth2"),
    path("accounts/logout/", views.logout, name="logout"),
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
        user_planning,
        name="accounts_user_planning",
    ),
    path(
        "users/<int:pk>/retrospective/",
        user_planning,
        {"retro": True},
        name="accounts_user_retrospective",
    ),
    path(
        "users/<int:pk>/statistics/",
        views.ProfileView.as_view(),
        name="accounts_user_statistics",
    ),
    # Teams
    path(
        "teams/",
        generic.ListView.as_view(model=Team, search_form_class=TeamSearchForm),
        name="accounts_team_list",
    ),
    path(
        "teams/<int:pk>/",
        generic.DetailView.as_view(model=Team),
        name="accounts_team_detail",
    ),
    path(
        "teams/create/",
        generic.CreateView.as_view(form_class=TeamForm, model=Team),
        name="accounts_team_create",
    ),
    path(
        "teams/<int:pk>/update/",
        generic.UpdateView.as_view(form_class=TeamForm, model=Team),
        name="accounts_team_update",
    ),
    path(
        "teams/<int:pk>/planning/",
        team_planning,
        name="accounts_team_planning",
    ),
    path(
        "teams/<int:pk>/retrospective/",
        team_planning,
        {"retro": True},
        name="accounts_team_retrospective",
    ),
    path(
        "teams/<int:pk>/delete/",
        generic.DeleteView.as_view(model=Team),
        name="accounts_team_delete",
    ),
]
