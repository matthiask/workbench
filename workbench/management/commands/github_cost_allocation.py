"""
Management command: github_cost_allocation

Fetches all issues from the configured GitHub project board, joins them with
workbench services and logged hours, and prints a tree-shaped cost breakdown
grouped by repository (billing unit). Optionally writes to XLSX or sends by mail.

Usage:
    uv run ./manage.py github_cost_allocation
    uv run ./manage.py github_cost_allocation --output report.xlsx
    uv run ./manage.py github_cost_allocation --mailto user@example.com
    uv run ./manage.py github_cost_allocation --project-url https://github.com/orgs/MY-ORG/projects/3
"""

from __future__ import annotations

import io
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management import BaseCommand
from django.utils.translation import activate

from workbench.projects.github_cost_allocation import (
    IssueNode,
    RepoGroup,
    billing_classification,
    build_tree,
    fetch_project_items,
    join_with_workbench,
)
from workbench.tools.formats import Z1
from workbench.tools.xlsx import WorkbenchXLSXDocument


class Command(BaseCommand):
    help = "Analyse GitHub project cost allocation and print a tree-shaped report."

    def add_arguments(self, parser):
        parser.add_argument(
            "--project-url",
            type=str,
            default=None,
            help="Override the project URL from settings.GITHUB_PROJECT_URLS[0].",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            metavar="FILE.xlsx",
            help="Write report to an XLSX file instead of stdout.",
        )
        parser.add_argument(
            "--mailto",
            type=str,
            default=None,
            metavar="EMAIL[,EMAIL]",
            help="Send the XLSX report by email to these addresses (comma-separated).",
        )

    def handle(self, *, project_url, output, mailto, **options):
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

        self.stdout.write(f"Fetching issues from {url} …")
        issues = fetch_project_items(url)
        self.stdout.write(f"  {len(issues)} issues fetched.")

        self.stdout.write("Joining with workbench data …")
        unmatched = join_with_workbench(issues)

        app_repos = getattr(settings, "GITHUB_APP_REPOS", {})
        groups = build_tree(issues, app_repos)

        if mailto:
            recipients = mailto.split(",")
            xlsx = _build_xlsx(groups, unmatched)
            mail = EmailMultiAlternatives(
                "GitHub Cost Allocation",
                "",
                to=recipients,
                reply_to=recipients,
            )
            with io.BytesIO() as f:
                xlsx.workbook.save(f)
                f.seek(0)
                mail.attach(
                    "github-cost-allocation.xlsx",
                    f.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            mail.send()
            self.stdout.write(f"Sent to {mailto}")
        elif output:
            xlsx = _build_xlsx(groups, unmatched)
            xlsx.workbook.save(output)
            self.stdout.write(f"Saved to {output}")
        else:
            _print_tree(groups, unmatched, self.stdout)


# ---------------------------------------------------------------------------
# Stdout output
# ---------------------------------------------------------------------------


def _print_tree(groups: list[RepoGroup], unmatched: list, out) -> None:
    for group in groups:
        out.write(f"\n{'=' * 70}")
        out.write(f"  {group.repo}")
        out.write(f"{'=' * 70}")

        if group.roots:
            for node in sorted(group.roots, key=lambda n: n.number):
                _print_node(node, out, depth=0)

        if group.cross_app_children:
            out.write("\n  ⚠ Cross-app parent links (excluded from rollup):")
            for node in group.cross_app_children:
                out.write(
                    f"    #{node.number} {node.title[:60]}"
                    f"  → parent in {node.parent_repo}"
                )

        est_offered, act_offered, est_add, act_add = _group_totals(group.roots)
        out.write(
            f"\n  Angeboten:   {est_offered:6.1f}h est  / {act_offered:6.1f}h actual"
        )
        out.write(f"  Zusätzlich:  {est_add:6.1f}h est  / {act_add:6.1f}h actual")

    if unmatched:
        out.write(f"\n\n{'=' * 70}")
        out.write("  Workbench services without GitHub issue")
        out.write(f"{'=' * 70}")
        for project, services in unmatched:
            out.write(f"\n  Project: {project}")
            for svc in services:
                logged = getattr(svc, "_logged_hours", Z1)
                est = svc.effort_hours or Z1
                offer_str = f"  offer: {svc.offer}" if svc.offer else ""
                out.write(
                    f"    [{svc.id:6d}]  est {est:5.1f}h  act {logged:5.1f}h"
                    f"{offer_str}  {svc.title[:60]}"
                )


def _print_node(node: IssueNode, out, depth: int) -> None:
    indent = "  " * depth
    classification = billing_classification(node)
    est = f"{node.estimate:5.1f}h" if node.estimate is not None else "     —"
    act = f"{node.logged_hours:5.1f}h"
    overrun = ""
    if node.estimate and node.logged_hours > node.estimate:
        overrun = " ⚠ overrun"
    state = "✓" if node.state == "CLOSED" else " "

    out.write(
        f"{indent}[{state}] #{node.number:4d}  [{classification:<30}]"
        f"  est {est}  act {act}{overrun}"
    )
    out.write(f"{indent}       {node.title[:70]}")

    if node.billing_label and node.billing_label_set_by:
        out.write(
            f"{indent}       label '{node.billing_label}' set by"
            f" {node.billing_label_set_by} at {node.billing_label_set_at}"
        )
    if node.offer:
        out.write(f"{indent}       offer: {node.offer}")

    for child in sorted(node.children, key=lambda n: n.number):
        _print_node(child, out, depth + 1)


def _group_totals(
    roots: list[IssueNode],
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    est_offered = act_offered = est_add = act_add = Z1

    def walk(node: IssueNode) -> None:
        nonlocal est_offered, act_offered, est_add, act_add
        cls = billing_classification(node)
        is_offered = cls.startswith("angeboten")
        if is_offered:
            est_offered += node.estimate or Z1
            act_offered += node.logged_hours
        else:
            est_add += node.estimate or Z1
            act_add += node.logged_hours
        for child in node.children:
            walk(child)

    for root in roots:
        walk(root)

    return est_offered, act_offered, est_add, act_add


# ---------------------------------------------------------------------------
# XLSX output
# ---------------------------------------------------------------------------

# Tree depth columns: one column per level, title placed in the matching column.
# Max depth observed in this project is ~3 (root → parent → child → grandchild).
_TREE_DEPTH = 4

_HEADERS = (
    ["Repo", "Issue"]
    + [f"L{i}" for i in range(1, _TREE_DEPTH + 1)]
    + [
        "Status",
        "Billing",
        "Label set by",
        "Label set at",
        "Own est. (h)",
        "Own logged (h)",
        "Total est. (h)",
        "Total logged (h)",
        "Delta (h)",
        "Offer",
        "Cross-app parent",
    ]
)
_NUM_COLS = len(_HEADERS)


def _build_xlsx(
    groups: list[RepoGroup], unmatched: list | None = None
) -> WorkbenchXLSXDocument:
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Font

    xlsx = WorkbenchXLSXDocument()
    xlsx.add_sheet("Cost Allocation")
    ws = xlsx.sheet

    def cell(value, *, bold=False):
        c = WriteOnlyCell(ws, value=value)
        if bold:
            c.font = Font(bold=True)
        return c

    def num(value, *, bold=False):
        if not value:
            return cell(None)
        c = WriteOnlyCell(ws, value=float(value))
        c.number_format = "0.0"
        if bold:
            c.font = Font(bold=True)
        return c

    def tree_cells(title, depth, *, bold=False):
        """Return _TREE_DEPTH cells with title in the depth-th slot, rest empty."""
        cols = [cell("") for _ in range(_TREE_DEPTH)]
        cols[min(depth, _TREE_DEPTH - 1)] = cell(title, bold=bold)
        return cols

    ws.append([cell(h, bold=True) for h in _HEADERS])

    for group in groups:
        ws.append(
            [cell(group.repo, bold=True), cell("")]
            + tree_cells(group.repo, 0, bold=True)
            + [cell("")] * (_NUM_COLS - 2 - _TREE_DEPTH)
        )

        for node in sorted(group.roots, key=lambda n: n.number):
            _xlsx_node_rows(
                node,
                group.repo,
                depth=0,
                ws=ws,
                cell=cell,
                num=num,
                tree_cells=tree_cells,
            )

        # Cross-app children — shown with warning, excluded from rollups
        for node in sorted(group.cross_app_children, key=lambda n: n.number):
            agg_est, agg_logged = _aggregate(node)
            ws.append([
                cell(group.repo),
                cell(f"#{node.number}"),
                *tree_cells(f"⚠ {node.title}", 0),
                cell(node.state),
                cell(billing_classification(node)),
                cell(node.billing_label_set_by or ""),
                cell(node.billing_label_set_at or ""),
                num(node.estimate),
                num(node.logged_hours),
                num(agg_est),
                num(agg_logged),
                num(agg_logged - agg_est if agg_est else None),
                cell(str(node.offer) if node.offer else ""),
                cell(node.parent_repo or ""),
            ])

        # Repo-level rollup rows: Angeboten / Zusätzlich totals
        est_off, act_off, est_add, act_add = _group_totals(group.roots)
        for label, est, act in [
            ("Total Angeboten", est_off, act_off),
            ("Total Zusätzlich", est_add, act_add),
        ]:
            ws.append([
                cell(""),
                cell(""),
                *tree_cells(label, 0, bold=True),
                cell(""),
                cell(""),
                cell(""),
                cell(""),
                cell(""),
                cell(""),  # no "own" concept for repo rollups
                num(est, bold=True),
                num(act, bold=True),
                num(act - est, bold=True),
                cell(""),
                cell(""),
            ])

        ws.append([cell("")] * _NUM_COLS)  # blank separator

    if unmatched:
        ws.append(
            [cell("Workbench services without GitHub issue", bold=True)]
            + [cell("")] * (_NUM_COLS - 1)
        )
        for project, services in unmatched:
            ws.append(
                [cell(str(project), bold=True), cell("")]
                + tree_cells(str(project), 0, bold=True)
                + [cell("")] * (_NUM_COLS - 2 - _TREE_DEPTH)
            )
            for svc in services:
                logged = getattr(svc, "_logged_hours", None)
                est = svc.effort_hours or None
                ws.append([
                    cell(""),
                    cell(f"[{svc.id}]"),
                    *tree_cells(svc.title, 1),
                    cell(""),  # Status
                    cell(""),  # Billing (no GitHub label)
                    cell(""),
                    cell(""),  # Label set by / at
                    num(est),  # Own est.
                    num(logged),  # Own logged
                    num(est),  # Total est. (= own; no children)
                    num(logged),  # Total logged
                    num((logged or Z1) - (est or Z1) if est else None),
                    cell(str(svc.offer) if svc.offer else ""),
                    cell(""),  # Cross-app parent
                ])
        ws.append([cell("")] * _NUM_COLS)

    return xlsx


def _aggregate(node: IssueNode) -> tuple[Decimal, Decimal]:
    """Return (total_estimate, total_logged) summed over this node and all descendants."""
    est = node.estimate or Z1
    logged = node.logged_hours
    for child in node.children:
        child_est, child_logged = _aggregate(child)
        est += child_est
        logged += child_logged
    return est, logged


def _xlsx_node_rows(node, repo, depth, *, ws, cell, num, tree_cells) -> None:
    is_parent = bool(node.children)
    agg_est, agg_logged = _aggregate(node)
    delta = agg_logged - agg_est if agg_est else None

    ws.append([
        cell(repo),
        cell(f"#{node.number}"),
        *tree_cells(node.title, depth, bold=is_parent),
        cell(node.state),
        cell(billing_classification(node)),
        cell(node.billing_label_set_by or ""),
        cell(node.billing_label_set_at or ""),
        num(node.estimate),  # own estimate
        num(node.logged_hours),  # own logged
        num(agg_est, bold=is_parent),  # total estimate (own + children)
        num(agg_logged, bold=is_parent),  # total logged (own + children)
        num(delta, bold=is_parent),
        cell(str(node.offer) if node.offer else ""),
        cell(""),
    ])

    for child in sorted(node.children, key=lambda n: n.number):
        _xlsx_node_rows(
            child, repo, depth + 1, ws=ws, cell=cell, num=num, tree_cells=tree_cells
        )


def _delta(node: IssueNode) -> Decimal | None:
    if node.estimate is None:
        return None
    return node.logged_hours - node.estimate
