from authlib.email import render_to_mail
from django.conf import settings
from django.core.management import BaseCommand
from django.db.models import Q
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

    def handle(self, **options):
        activate("de")

        found_issues, updated_issues, estimates = update_service_estimates()

        if not updated_issues:
            return

        mail = render_to_mail(
            "projects/update_service_estimates",
            {
                "found_issues": found_issues,
                "updated_issues": updated_issues,
                "missing_issues": sorted(
                    (issue_url, estimates[issue_url])
                    for issue_url in set(estimates) - found_issues
                ),
                "WORKBENCH": settings.WORKBENCH,
            },
            to=options["mailto"].split(","),
        )
        mail.send()


def update_service_estimates():
    set_user_name("GitHub estimates integration")

    offers = set()
    found_issues = set()
    updated_issues = set()
    estimates = {}

    for project_url in settings.GITHUB_PROJECT_URLS:
        estimates |= issue_estimates_from_github_project(project_url)

        q = Q(id=0)
        for issue_url in estimates:
            q |= Q(description__icontains=issue_url)

        editable = (
            Service.objects.filter(
                project__in=Project.objects.open(),
            )
            .editable()
            .filter(q)
            .select_related("offer")
        )

        for service in editable:
            for issue_url, estimate in estimates.items():
                if issue_url.lower() not in service.description.lower():
                    continue

                found_issues.add((issue_url, estimate, service))
                if service.effort_hours != estimate:
                    service.effort_hours = estimate
                    service.save(skip_related_model=True)
                    offers.add(service.offer)

                    updated_issues.add((issue_url, estimate, service))

    offers.discard(None)
    for offer in offers:
        offer.save()

    return found_issues, updated_issues, estimates
