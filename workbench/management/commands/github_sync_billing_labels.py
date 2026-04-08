"""
Management command: github_sync_billing_labels

Walks the GitHub project issue tree and syncs the angeboten/zusätzlich labels
based on parent-chain relationships and workbench offer status:

  - Issue or ancestor has a workbench service with an ACCEPTED offer → angeboten
  - Ancestor has a workbench service with a non-accepted offer → remove both labels
  - No ancestor has a workbench service → zusätzlich

Usage:
    uv run ./manage.py github_sync_billing_labels
    uv run ./manage.py github_sync_billing_labels --dry-run
"""

from __future__ import annotations

import logging
import re

import requests
from django.conf import settings
from django.core.management import BaseCommand
from django.utils.translation import activate

from workbench.projects.github_cost_allocation import (
    IssueNode,
    build_tree,
    fetch_project_items,
    join_with_workbench,
)


logger = logging.getLogger(__name__)

_BILLING_LABELS = {"angeboten", "zusätzlich"}
_ISSUE_URL_RE = re.compile(
    r"https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/issues/(?P<number>\d+)"
)


def _has_accepted_offer(node: IssueNode) -> bool:
    return (
        node.service is not None
        and node.service.offer is not None
        and node.service.offer.is_accepted
    )


def _has_pending_offer(node: IssueNode) -> bool:
    return (
        node.service is not None
        and node.service.offer is not None
        and not node.service.offer.is_accepted
    )


def _walk(
    node: IssueNode, *, ancestor_accepted: bool = False, ancestor_pending: bool = False
):
    """Yield (node, desired_label) for this node and all descendants."""
    own_accepted = _has_accepted_offer(node)
    own_pending = _has_pending_offer(node)

    if own_accepted or ancestor_accepted:
        desired: str | None = "angeboten"
    elif own_pending or ancestor_pending:
        desired = None  # offer exists but not accepted — leave unlabeled
    else:
        desired = "zusätzlich"

    yield node, desired

    child_accepted = ancestor_accepted or own_accepted
    child_pending = (not child_accepted) and (ancestor_pending or own_pending)
    for child in node.children:
        yield from _walk(
            child, ancestor_accepted=child_accepted, ancestor_pending=child_pending
        )


def _sync_nodes(nodes, headers, out, dry_run):
    """Apply label changes for an iterable of root nodes. Returns (adds, removes, skips)."""
    adds = removes = skips = 0
    for root in nodes:
        for node, desired in _walk(root):
            current = set(node.labels) & _BILLING_LABELS
            desired_set = {desired} if desired else set()
            to_add = desired_set - current
            to_remove = current - desired_set

            if not to_add and not to_remove:
                skips += 1
                continue

            m = _ISSUE_URL_RE.match(node.url)
            if not m:
                continue
            owner = m.group("owner")
            repo = m.group("repo")
            number = int(m.group("number"))
            desc = f"{repo}#{node.number} {node.title[:50]}"

            for label in to_add:
                out.write(f"  + {label:<12} {desc}")
                if not dry_run:
                    _add_label(owner, repo, number, label, headers)
                adds += 1
            for label in to_remove:
                out.write(f"  - {label:<12} {desc}")
                if not dry_run:
                    _remove_label(owner, repo, number, label, headers)
                removes += 1

    return adds, removes, skips


class Command(BaseCommand):
    help = (
        "Sync angeboten/zusätzlich labels from workbench offer status + parent chain."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--project-url",
            default=None,
            help="Override settings.GITHUB_PROJECT_URLS[0].",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print planned changes without making any API calls.",
        )

    def handle(self, *, project_url, dry_run, **options):
        activate("de")

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

        token = getattr(settings, "GITHUB_API_TOKEN", "")
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }

        self.stdout.write(f"Fetching issues from {url} …")
        issues = fetch_project_items(url)
        self.stdout.write(f"  {len(issues)} issues fetched.")

        self.stdout.write("Joining with workbench data …")
        join_with_workbench(issues)

        app_repos = getattr(settings, "GITHUB_APP_REPOS", {})
        groups = build_tree(issues, app_repos)

        total_adds = total_removes = total_skips = 0
        for group in groups:
            # Roots: inherit offer context down the tree
            a, r, s = _sync_nodes(group.roots, headers, self.stdout, dry_run)
            total_adds += a
            total_removes += r
            total_skips += s
            # Cross-app children: no inherited context from their (cross-app) parent
            a, r, s = _sync_nodes(
                group.cross_app_children, headers, self.stdout, dry_run
            )
            total_adds += a
            total_removes += r
            total_skips += s

        suffix = " (dry run)" if dry_run else ""
        self.stdout.write(
            f"\nDone{suffix}: {total_adds} added, {total_removes} removed, {total_skips} unchanged."
        )


def _add_label(owner, repo, number, label, headers):
    resp = requests.post(
        f"https://api.github.com/repos/{owner}/{repo}/issues/{number}/labels",
        json={"labels": [label]},
        headers=headers,
    )
    if not resp.ok:
        logger.warning(
            "Failed to add label %r to %s/%s#%s: %s",
            label,
            owner,
            repo,
            number,
            resp.text,
        )


def _remove_label(owner, repo, number, label, headers):
    resp = requests.delete(
        f"https://api.github.com/repos/{owner}/{repo}/issues/{number}/labels/{label}",
        headers=headers,
    )
    if not resp.ok and resp.status_code != 404:
        logger.warning(
            "Failed to remove label %r from %s/%s#%s: %s",
            label,
            owner,
            repo,
            number,
            resp.text,
        )
