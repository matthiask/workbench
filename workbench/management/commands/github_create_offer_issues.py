"""
Management command: github_create_offer_issues

For a given accepted offer, creates one GitHub issue per service, adds each
issue to the project board, and sets the Workbench (service ID) and Estimate
fields. The issue URL is also written to the service description so the
URL-based matching fallback continues to work.

Usage:
    uv run ./manage.py github_create_offer_issues <offer_pk> --repo REPO_NAME
    uv run ./manage.py github_create_offer_issues <offer_pk> --repo REPO_NAME --dry-run
"""

from __future__ import annotations

from django.conf import settings
from django.core.management import BaseCommand
from django.utils.translation import activate

from workbench.projects.github_cost_allocation import create_issue_on_project


class Command(BaseCommand):
    help = "Create GitHub issues for each service in an accepted offer."

    def add_arguments(self, parser):
        parser.add_argument("offer_pk", type=int, help="Offer primary key.")
        parser.add_argument(
            "--repo",
            required=True,
            metavar="REPO_NAME",
            help="GitHub repository name to create issues in (within the configured org).",
        )
        parser.add_argument(
            "--project-url",
            default=None,
            help="Override settings.GITHUB_PROJECT_URLS[0].",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be created without making any API calls.",
        )

    def handle(self, *, offer_pk, repo, project_url, dry_run, **options):
        activate("de")

        from workbench.offers.models import Offer

        try:
            offer = (
                Offer.objects
                .select_related("project__owned_by")
                .prefetch_related("services")
                .get(pk=offer_pk)
            )
        except Offer.DoesNotExist:
            self.stderr.write(f"Offer {offer_pk} not found.")
            return

        url = project_url or (
            settings.GITHUB_PROJECT_URLS[0]
            if getattr(settings, "GITHUB_PROJECT_URLS", [])
            else None
        )
        if not url:
            self.stderr.write(
                "No project URL configured. Use --project-url or set GITHUB_PROJECT_URLS."
            )
            return

        getattr(settings, "GITHUB_APP_REPOS", {})
        org = next(
            (
                settings.GITHUB_APP_REPOS.get("org", None)
                for _ in [None]  # just to use next()
            ),
            None,
        )
        # Derive org from the project URL (orgs/<org>/projects/<n>)
        import re

        m = re.search(r"github\.com/orgs/([^/]+)/", url)
        org = m.group(1) if m else None
        if not org:
            self.stderr.write(f"Could not determine GitHub org from project URL: {url}")
            return

        services = list(offer.services.order_by("position", "created_at"))
        if not services:
            self.stderr.write(f"Offer {offer_pk} has no services.")
            return

        self.stdout.write(
            f"{'[DRY RUN] ' if dry_run else ''}Creating {len(services)} issue(s) "
            f"for offer {offer} in {org}/{repo} …"
        )

        for svc in services:
            # Skip services already linked via external_reference or description
            if svc.external_reference or "github.com" in (svc.description or ""):
                self.stdout.write(f"  skip  [{svc.id}] {svc.title} — already linked")
                continue

            body = svc.description or ""

            issue_url = create_issue_on_project(
                owner=org,
                repo=repo,
                project_url=url,
                title=svc.title,
                body=body,
                estimate=float(svc.effort_hours) if svc.effort_hours else None,
                dry_run=dry_run,
            )

            if issue_url:
                self.stdout.write(f"  created [{svc.id}] {svc.title} → {issue_url}")
                svc.external_reference = issue_url
                svc.save(update_fields=["external_reference"])
            elif not dry_run:
                self.stderr.write(f"  FAILED [{svc.id}] {svc.title}")
