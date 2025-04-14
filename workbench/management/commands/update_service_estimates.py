import sentry_sdk
from authlib.email import render_to_mail
from django.conf import settings
from django.core.management import BaseCommand
from django.utils.translation import activate

from workbench.accounts.middleware import set_user_name
from workbench.projects.github import issue_estimates_from_github_project
from workbench.projects.models import Project, Service


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--mailto",
            type=str,
        )

    def handle(self, *, mailto, **options):
        activate("de")

        try:
            up_to_date_issues, updated_issues, estimates = update_service_estimates()
        except Exception as exc:
            sentry_sdk.capture_exception(exc)

        if updated_issues and mailto:
            mail = render_to_mail(
                "projects/update_service_estimates",
                {
                    "up_to_date_issues": sorted(up_to_date_issues.items()),
                    "updated_issues": sorted(updated_issues.items()),
                    "missing_issues": sorted(
                        (issue_url, estimates[issue_url])
                        for issue_url in set(estimates)
                        - set(up_to_date_issues)
                        - set(updated_issues)
                    ),
                    "WORKBENCH": settings.WORKBENCH,
                },
                to=mailto.split(","),
            )
            mail.send()


def update_service_estimates():
    set_user_name("GitHub estimates integration")

    offers = set()
    up_to_date_issues = {}
    updated_issues = {}
    estimates = {}

    for project_url in settings.GITHUB_PROJECT_URLS:
        estimates |= issue_estimates_from_github_project(project_url)

        editable = (
            Service.objects.filter(
                project__in=Project.objects.open(),
            )
            .editable()
            .filter(description__icontains="github.com")
            .select_related("offer", "project__owned_by")
        )

        for service in editable:
            for issue_url, estimate in estimates.items():
                if issue_url.lower() not in service.description.lower():
                    continue

                if service.effort_hours == estimate:
                    up_to_date_issues[issue_url] = service
                else:
                    service.effort_hours = estimate
                    service.save(skip_related_model=True)
                    offers.add(service.offer)
                    updated_issues[issue_url] = service

    offers.discard(None)
    for offer in offers:
        offer.save()

    return up_to_date_issues, updated_issues, estimates
