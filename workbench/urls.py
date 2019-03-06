from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from django.shortcuts import render

from workbench import views
from workbench.awt.views import ReportView
from workbench.reporting.views import monthly_invoicing, overdrawn_projects


urlpatterns = [
    url(r"^$", render, {"template_name": "start.html"}),
    url(r"^404/$", render, {"template_name": "404.html"}),
    url(r"^admin/", admin.site.urls),
    url(r"^accounts/", include("workbench.accounts.urls")),
    url(r"^activities/", include("workbench.activities.urls")),
    url(r"^contacts/", include("workbench.contacts.urls")),
    url(r"^deals/", include("workbench.deals.urls")),
    url(r"^logbook/", include("workbench.logbook.urls")),
    url(r"^absences/", include("workbench.awt.urls")),
    url(r"^offers/", include("workbench.offers.urls")),
    url(r"^projects/", include("workbench.projects.urls")),
    url(r"^invoices/", include("workbench.invoices.urls")),
    url(r"^recurring-invoices/", include("workbench.invoices.recurring_urls")),
    url(r"^search/$", views.search, name="search"),
    url(r"^history/(\w+\.\w+)/([0-9]+)/$", views.history, name="history"),
    #
    # Reports
    url(r"^report/annual-working-time/$", ReportView.as_view(), name="awt_year_report"),
    url(
        r"^report/monthly-invoicing/$",
        monthly_invoicing,
        name="report_monthly_invoicing",
    ),
    url(
        r"^report/overdrawn-projects/$",
        overdrawn_projects,
        name="report_overdrawn_projects",
    ),
]

if settings.DEBUG:
    import debug_toolbar
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns = (
        urlpatterns
        + [url(r"^__debug__/", include(debug_toolbar.urls))]
        + staticfiles_urlpatterns()
    )
