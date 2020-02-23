from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.shortcuts import render
from django.urls import path
from django.views.i18n import JavaScriptCatalog

from workbench import views


urlpatterns = [
    url(r"^$", render, {"template_name": "start.html"}),
    url(r"^404/$", render, {"template_name": "404.html"}),
    url(r"^shortcuts/$", render, {"template_name": "shortcuts.html"}, name="shortcuts"),
    url(r"^admin/", admin.site.urls),
    url(r"^accounts/", include("workbench.accounts.urls")),
    url(r"^contacts/", include("workbench.contacts.urls")),
    url(r"^logbook/", include("workbench.logbook.urls")),
    url(r"^absences/", include("workbench.awt.urls")),
    url(r"^offers/", include("workbench.offers.urls")),
    url(r"^projects/", include("workbench.projects.urls")),
    url(r"^invoices/", include("workbench.invoices.urls")),
    url(r"^recurring-invoices/", include("workbench.invoices.recurring_urls")),
    url(r"^credit-control/", include("workbench.credit_control.urls")),
    url(r"^expenses/", include("workbench.expenses.urls")),
    url(r"^deals/", include("workbench.deals.urls")),
    url(r"^search/$", views.search, name="search"),
    url(r"^history/(\w+)/(\w+)/([0-9]+)/$", views.history, name="history"),
    url(r"^report/", include("workbench.reporting.urls")),
    url(r"", include("workbench.timer.urls")),
]

urlpatterns += i18n_patterns(
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
)

if settings.DEBUG:  # pragma: no cover
    import debug_toolbar
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns = (
        urlpatterns
        + [url(r"^__debug__/", include(debug_toolbar.urls))]
        + staticfiles_urlpatterns()
    )
