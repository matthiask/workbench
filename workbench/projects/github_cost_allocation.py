"""
Cost allocation analysis for GitHub Projects v2.

Fetches all issues from the configured project, joins them with workbench
services and logged hours, and builds a tree grouped by repository (billing
unit boundary) with parent-child hierarchy within each group.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal

import requests
from django.conf import settings
from django.db.models import Sum

from workbench.tools.formats import Z1


logger = logging.getLogger(__name__)

BILLING_LABELS = {"angeboten", "zusätzlich"}


@dataclass
class IssueNode:
    url: str
    repo: str
    number: int
    title: str
    state: str
    estimate: Decimal | None
    labels: list[str]
    archived: bool = False

    # Attribution for billing label
    billing_label: str | None = None  # 'angeboten' | 'zusätzlich' | None
    billing_label_set_by: str | None = None  # GitHub login
    billing_label_set_at: str | None = None  # ISO datetime string

    # Hierarchy
    parent_url: str | None = None
    parent_repo: str | None = None
    children: list[IssueNode] = field(default_factory=list)

    # Workbench data (filled in by join_with_workbench)
    service: object = None  # projects.Service or None
    logged_hours: Decimal = Z1
    offer: object = None  # offers.Offer or None


@dataclass
class RepoGroup:
    repo: str
    roots: list[IssueNode] = field(default_factory=list)
    cross_app_children: list[IssueNode] = field(default_factory=list)


def _gql(query, variables, headers):
    resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=headers,
    )
    resp.raise_for_status()
    data = resp.json()
    if errors := data.get("errors"):
        for err in errors:
            logger.warning("GraphQL error: %s", err.get("message"))
    return data.get("data", {})


def _get_project_id(org, number, headers):
    data = _gql(
        """
        query($org: String!, $number: Int!) {
          organization(login: $org) {
            projectV2(number: $number) { id }
          }
        }
        """,
        {"org": org, "number": number},
        headers,
    )
    return data["organization"]["projectV2"]["id"]


_ITEMS_QUERY = """
query($projectId: ID!, $after: String) {
  node(id: $projectId) {
    ... on ProjectV2 {
      items(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          isArchived
          fieldValues(first: 20) {
            nodes {
              ... on ProjectV2ItemFieldNumberValue {
                number
                field { ... on ProjectV2FieldCommon { name } }
              }
            }
          }
          content {
            ... on Issue {
              number
              title
              state
              url
              labels(first: 15) { nodes { name } }
              repository { name }
              parent {
                url
                repository { name }
              }
            }
          }
        }
      }
    }
  }
}
"""

_TIMELINE_QUERY = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    issue(number: $number) {
      timelineItems(first: 50, itemTypes: [LABELED_EVENT, UNLABELED_EVENT]) {
        nodes {
          __typename
          ... on LabeledEvent {
            createdAt
            actor { login }
            label { name }
          }
          ... on UnlabeledEvent {
            createdAt
            actor { login }
            label { name }
          }
        }
      }
    }
  }
}
"""


def fetch_project_items(project_url: str) -> list[IssueNode]:
    """
    Fetch all issues from a GitHub Projects v2 board, with estimates,
    labels, and parent relationships.
    """
    from workbench.projects.github import extract_project_info

    token = getattr(settings, "GITHUB_API_TOKEN", "")
    if not token:
        logger.error("GITHUB_API_TOKEN not set")
        return []

    headers = {"Authorization": f"token {token}"}
    org, _repo, number_str = extract_project_info(project_url)
    if not org or not number_str:
        return []

    project_id = _get_project_id(org, int(number_str), headers)
    nodes = []
    after = None

    while True:
        data = _gql(_ITEMS_QUERY, {"projectId": project_id, "after": after}, headers)
        items_data = data["node"]["items"]
        nodes.extend(items_data["nodes"])
        if not items_data["pageInfo"]["hasNextPage"]:
            break
        after = items_data["pageInfo"]["endCursor"]

    issues = []
    for item in nodes:
        content = item.get("content") or {}
        if "number" not in content:
            continue  # draft or PR

        # Extract estimate from field values
        estimate = None
        for fv in item.get("fieldValues", {}).get("nodes", []):
            fname = fv.get("field", {}).get("name", "").lower()
            if "number" in fv and any(
                t in fname for t in ["hour", "estimate", "time", "duration"]
            ):
                estimate = Decimal(str(fv["number"]))
                break

        labels = [n["name"] for n in content.get("labels", {}).get("nodes", [])]
        billing_label = next((lb for lb in labels if lb in BILLING_LABELS), None)

        parent = content.get("parent")
        issues.append(
            IssueNode(
                url=content["url"],
                repo=content["repository"]["name"],
                number=content["number"],
                title=content["title"],
                state=content["state"],
                estimate=estimate,
                labels=labels,
                billing_label=billing_label,
                archived=item.get("isArchived", False),
                parent_url=parent["url"] if parent else None,
                parent_repo=parent["repository"]["name"] if parent else None,
            )
        )

    # Fetch attribution for issues that have a billing label
    _fetch_billing_label_attribution(
        [i for i in issues if i.billing_label],
        org,
        headers,
    )

    return issues


def _fetch_billing_label_attribution(
    issues: list[IssueNode], org: str, headers: dict
) -> None:
    """Fill in billing_label_set_by / billing_label_set_at for issues with billing labels."""
    for issue in issues:
        data = _gql(
            _TIMELINE_QUERY,
            {"owner": org, "repo": issue.repo, "number": issue.number},
            headers,
        )
        events = (
            data
            .get("repository", {})
            .get("issue", {})
            .get("timelineItems", {})
            .get("nodes", [])
        )

        # Find the most recent LabeledEvent for the billing label (it may have been
        # removed and re-added; last add wins).
        last_add = None
        for ev in events:
            if (
                ev.get("__typename") == "LabeledEvent"
                and ev.get("label", {}).get("name") == issue.billing_label
            ):
                last_add = ev

        if last_add:
            issue.billing_label_set_by = (last_add.get("actor") or {}).get("login")
            issue.billing_label_set_at = last_add.get("createdAt")


_ISSUE_URL_RE = re.compile(
    r"https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/issues/(?P<number>\d+)"
)

_ISSUE_FRAGMENT = """
      number
      title
      state
      url
      labels(first: 15) { nodes { name } }
      repository { name }
      parent {
        url
        repository { name }
      }
"""


def _fetch_issues_batch(
    refs: list[tuple[str, str, int]],  # (owner, repo, number)
    headers: dict,
) -> list[IssueNode]:
    """
    Fetch multiple issues in a single GraphQL request using aliases.
    Groups by repo; builds one aliased query per batch.
    Returns IssueNode list (estimate=None; caller fills it from workbench).
    """
    from collections import defaultdict

    # group by (owner, repo) → list of numbers
    by_repo: dict[tuple[str, str], list[int]] = defaultdict(list)
    for owner, repo, number in refs:
        by_repo[(owner, repo)].append(number)

    # Build one big aliased query — GitHub handles hundreds of aliases fine
    lines = ["query {"]
    alias_map: dict[str, tuple[str, str, int]] = {}  # alias → (owner, repo, number)
    for repo_idx, ((owner, repo), numbers) in enumerate(by_repo.items()):
        repo_alias = f"r{repo_idx}"
        lines.append(f'  {repo_alias}: repository(owner: "{owner}", name: "{repo}") {{')
        for number in numbers:
            issue_alias = f"i{number}"
            lines.append(
                f"    {issue_alias}: issue(number: {number}) {{{_ISSUE_FRAGMENT}    }}"
            )
            alias_map[f"{repo_alias}.{issue_alias}"] = (owner, repo, number)
        lines.append("  }")
    lines.append("}")
    query = "\n".join(lines)

    data = _gql(query, {}, headers)

    nodes = []
    needs_attribution = []
    for repo_idx, ((owner, _repo), numbers) in enumerate(by_repo.items()):
        repo_alias = f"r{repo_idx}"
        repo_data = data.get(repo_alias) or {}
        for number in numbers:
            content = repo_data.get(f"i{number}")
            if not content:
                continue
            labels = [n["name"] for n in content.get("labels", {}).get("nodes", [])]
            billing_label = next((lb for lb in labels if lb in BILLING_LABELS), None)
            parent = content.get("parent")
            node = IssueNode(
                url=content["url"],
                repo=content["repository"]["name"],
                number=content["number"],
                title=content["title"],
                state=content["state"],
                estimate=None,  # filled by caller from service.effort_hours
                labels=labels,
                billing_label=billing_label,
                archived=True,
                parent_url=parent["url"] if parent else None,
                parent_repo=parent["repository"]["name"] if parent else None,
            )
            nodes.append(node)
            if billing_label:
                needs_attribution.append((node, owner))

    for node, owner in needs_attribution:
        _fetch_billing_label_attribution([node], owner, headers)

    return nodes


def build_tree(
    issues: list[IssueNode],
    app_repos: dict[str, list[str]] | None = None,
) -> list[RepoGroup]:
    """
    Resolve parent-child relationships and group by repository.

    Cross-app parent links (parent in a different app group) are noted on
    the node but the issue is placed as a root in its own repo group.
    Same-app cross-repo parent links are followed normally.

    app_repos: {"002": ["Englisch-Erprobung", ...], "005": [...]}
    """
    app_repos = app_repos or getattr(settings, "GITHUB_APP_REPOS", {})

    # Repo → app group mapping
    repo_to_app = {repo: app for app, repos in app_repos.items() for repo in repos}

    by_url = {issue.url: issue for issue in issues}

    # Attach children to parents; mark cross-app links
    for issue in issues:
        if not issue.parent_url:
            continue
        parent = by_url.get(issue.parent_url)
        if parent is None:
            continue  # parent not in project board — treat as root

        child_app = repo_to_app.get(issue.repo)
        parent_app = repo_to_app.get(issue.parent_repo or parent.repo)

        if child_app and parent_app and child_app != parent_app:
            # Cross-app: don't attach, leave as root with warning flag
            issue.parent_url = issue.parent_url  # keep for display
            issue.parent_repo = issue.parent_repo
            # Signal cross-app by leaving it detached
            continue

        parent.children.append(issue)

    # Identify roots: issues with no parent in the project, or with a cross-app parent
    attached = {child.url for issue in issues for child in issue.children}
    roots = [i for i in issues if i.url not in attached]

    # Group roots by repo
    repo_groups: dict[str, RepoGroup] = {}
    for issue in roots:
        if issue.repo not in repo_groups:
            repo_groups[issue.repo] = RepoGroup(repo=issue.repo)

        cross_app = (
            issue.parent_url is not None
            and issue.parent_repo is not None
            and repo_to_app.get(issue.repo) != repo_to_app.get(issue.parent_repo)
        )
        if cross_app:
            repo_groups[issue.repo].cross_app_children.append(issue)
        else:
            repo_groups[issue.repo].roots.append(issue)

    return sorted(repo_groups.values(), key=lambda g: g.repo)


def join_with_workbench(
    issues: list[IssueNode],
) -> list:
    """
    Match each IssueNode to a workbench Service (by issue URL in description),
    and attach logged hours and offer data. Modifies issues in-place.

    For services whose GitHub issue is not on the project board (e.g. archived),
    fetches the issue directly from the GitHub API and appends it to `issues`.

    Returns a list of (project, [service, ...]) pairs for services in the same
    workbench projects that were not matched to any GitHub issue.
    """
    from collections import defaultdict

    from workbench.logbook.models import LoggedHours
    from workbench.projects.models import Service

    token = getattr(settings, "GITHUB_API_TOKEN", "")
    headers = {"Authorization": f"token {token}"} if token else {}

    github_services = list(
        Service.objects.filter(description__icontains="github.com").select_related(
            "offer", "project__owned_by"
        )
    )
    logged = {
        row["service"]: row["hours__sum"]
        for row in LoggedHours.objects
        .filter(service__in=[s.id for s in github_services])
        .values("service")
        .annotate(hours__sum=Sum("hours"))
    }

    matched_ids = set()
    for issue in issues:
        for service in github_services:
            if issue.url.lower() in service.description.lower():
                issue.service = service
                issue.logged_hours = logged.get(service.id, Z1)
                issue.offer = service.offer
                matched_ids.add(service.id)
                break

    # For services not yet matched, batch-fetch their issues directly (handles archived).
    if token:
        known_urls = {issue.url.lower() for issue in issues}
        refs = []
        ref_to_service = {}
        for service in github_services:
            if service.id in matched_ids:
                continue
            m = _ISSUE_URL_RE.search(service.description)
            if not m:
                continue
            if m.group(0).lower() in known_urls:
                continue  # URL known but didn't match text — skip
            key = (m.group("owner"), m.group("repo"), int(m.group("number")))
            refs.append(key)
            ref_to_service[key] = service

        if refs:
            for node in _fetch_issues_batch(refs, headers):
                key = (
                    # owner isn't on IssueNode; derive from url
                    _ISSUE_URL_RE.search(node.url).group("owner"),
                    node.repo,
                    node.number,
                )
                service = ref_to_service.get(key)
                if service:
                    node.estimate = service.effort_hours
                    node.service = service
                    node.logged_hours = logged.get(service.id, Z1)
                    node.offer = service.offer
                    matched_ids.add(service.id)
                issues.append(node)
                known_urls.add(node.url.lower())

    # Find projects that had at least one matched service, then collect
    # all other services from those same projects.
    matched_projects = {s.project_id for s in github_services if s.id in matched_ids}
    if not matched_projects:
        return []

    all_project_services = list(
        Service.objects
        .filter(project__in=matched_projects)
        .exclude(id__in=matched_ids)
        .select_related("offer", "project__owned_by")
        .order_by("project", "position")
    )
    unmatched_logged = {
        row["service"]: row["hours__sum"]
        for row in LoggedHours.objects
        .filter(service__in=[s.id for s in all_project_services])
        .values("service")
        .annotate(hours__sum=Sum("hours"))
    }
    for service in all_project_services:
        service._logged_hours = unmatched_logged.get(service.id, Z1)

    by_project = defaultdict(list)
    for service in all_project_services:
        by_project[service.project].append(service)

    return sorted(by_project.items(), key=lambda p: str(p[0]))


def billing_classification(issue: IssueNode) -> str:
    """
    Derive the billing classification for display.

    Priority: workbench offer status (authoritative for billing) is shown
    alongside the GitHub label, and mismatches are flagged.
    """

    has_offer = issue.offer is not None
    offer_accepted = has_offer and issue.offer.is_accepted
    offer_declined = has_offer and issue.offer.is_declined

    label = issue.billing_label  # 'angeboten' | 'zusätzlich' | None

    if offer_accepted and label == "angeboten":
        return "angeboten"
    if offer_accepted and label != "angeboten":
        return "angeboten ⚠ label fehlt"
    if not offer_accepted and label == "angeboten":
        return "angeboten (Angebot ausstehend)"
    if label == "zusätzlich" or (not has_offer and label is None):
        return "zusätzlich" if label == "zusätzlich" else "—"
    if offer_declined:
        return "zusätzlich (Angebot abgelehnt)"
    return "—"
