from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.shortcuts import redirect, render
from django.urls import include, path, re_path
from django.views.i18n import JavaScriptCatalog

from workbench import views


admin.site.enable_nav_sidebar = False


urlpatterns = [
    re_path(r"^$", views.start),
    re_path(r"^404/$", render, {"template_name": "404.html"}),
    re_path(
        r"^shortcuts/$", render, {"template_name": "shortcuts.html"}, name="shortcuts"
    ),
    re_path(r"^admin/", admin.site.urls),
    re_path(r"", include("workbench.accounts.urls")),
    re_path(r"^contacts/", include("workbench.contacts.urls")),
    re_path(r"^logbook/", include("workbench.logbook.urls")),
    re_path(r"^absences/", include("workbench.awt.urls")),
    re_path(r"^projects/", include("workbench.projects.urls")),
    re_path(r"^invoices/", include("workbench.invoices.urls")),
    re_path(r"^recurring-invoices/", include("workbench.invoices.recurring_urls")),
    re_path(r"^credit-control/", include("workbench.credit_control.urls")),
    re_path(r"^expenses/", include("workbench.expenses.urls")),
    re_path(r"^deals/", include("workbench.deals.urls")),
    re_path(r"^planning/", include("workbench.planning.urls")),
    re_path(r"^search/$", views.search, name="search"),
    re_path(r"^history/(\w+)/(\w+)/([0-9]+)/$", views.history, name="history"),
    re_path(r"^report/", include("workbench.reporting.urls")),
    re_path(r"", include("workbench.timer.urls")),
    re_path(r"^notes/", include("workbench.notes.urls")),
    # Legacy URL redirects
    re_path(
        r"^projects/projects/([0-9]+)/$",
        lambda request, pk: redirect("projects_project_detail", pk=pk),
    ),
    re_path(
        r"^offers/([0-9]+)/$",
        lambda request, pk: redirect("offers_offer_detail", pk=pk),
    ),
]

urlpatterns += i18n_patterns(
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
)

if settings.DEBUG_TOOLBAR:  # pragma: no cover
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    import debug_toolbar

    urlpatterns = (
        urlpatterns
        + [re_path(r"^__debug__/", include(debug_toolbar.urls))]
        + staticfiles_urlpatterns()
    )
