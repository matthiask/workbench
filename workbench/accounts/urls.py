from django.shortcuts import redirect
from django.urls import path, re_path

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
        "user/",
        lambda request: redirect("accounts_user_detail", pk=request.user.pk),
        name="accounts_user_redirect_to_self",
    ),
    path("user/<int:pk>/", views.ProfileView.as_view(), name="accounts_user_detail"),
    path(
        "user/<int:pk>/planning/",
        UserPlanningView.as_view(),
        name="accounts_user_planning",
    ),
]
