from django.shortcuts import redirect
from django.urls import path, re_path

from workbench import generic
from workbench.accounts.forms import UserSearchForm
from workbench.accounts.models import User
from workbench.planning.views import UserPlanningView

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
            model=User, search_form_class=UserSearchForm, show_create_button=False,
        ),
        name="accounts_user_list",
    ),
    path(
        "users/<int:pk>/",
        lambda request, pk: redirect("planning/"),
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
]
