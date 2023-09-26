from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.shortcuts import redirect, render
from django.urls import include, path, re_path
from django.views.i18n import JavaScriptCatalog

from workbench import views


admin.site.enable_nav_sidebar = False


urlpatterns = [
    path("", views.start),
    path("404/", render, {"template_name": "404.html"}),
    path("shortcuts/", render, {"template_name": "shortcuts.html"}, name="shortcuts"),
    re_path(r"^admin/", admin.site.urls),
    path("", include("workbench.accounts.urls")),
    path("contacts/", include("workbench.contacts.urls")),
    path("logbook/", include("workbench.logbook.urls")),
    path("absences/", include("workbench.awt.urls")),
    path("projects/", include("workbench.projects.urls")),
    path("invoices/", include("workbench.invoices.urls")),
    path("recurring-invoices/", include("workbench.invoices.recurring_urls")),
    path("credit-control/", include("workbench.credit_control.urls")),
    path("expenses/", include("workbench.expenses.urls")),
    path("deals/", include("workbench.deals.urls")),
    path("planning/", include("workbench.planning.urls")),
    path("search/", views.search, name="search"),
    re_path(r"^history/(\w+)/(\w+)/([0-9]+)/$", views.history, name="history"),
    path("report/", include("workbench.reporting.urls")),
    path("", include("workbench.timer.urls")),
    path("notes/", include("workbench.notes.urls")),
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
    import debug_toolbar
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns = [
        *urlpatterns,
        path("__debug__/", include(debug_toolbar.urls)),
        *staticfiles_urlpatterns(),
    ]
