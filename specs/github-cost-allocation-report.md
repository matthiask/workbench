# GitHub Cost Allocation Report — Specification

## Goal

A tree-shaped cost breakdown per GitHub project that shows:
- Whether each issue/service was part of an **accepted offer** or is an **additional charge**
- Estimate vs. actual logged hours, per issue and rolled up to parent issues
- Which issues belong together (parent → child hierarchy)

The existing project statistics XLSX shows cost per service and month but has no notion of
offer vs. additional, and no hierarchy. This report replaces or supplements it for client
cost discussions.

---

## Data Sources

### GitHub Projects v2

**Custom project fields used:**

| Field | Type | Notes |
|---|---|---|
| `Estimate` | Number | Hours estimate — read from board; written by `github_create_offer_issues` |

Other fields (`Status`, `Happy Date`, `Annotations`, etc.) are available but not currently
used by the report.

**Native issue hierarchy:**

The GraphQL schema exposes `Issue.parent` — the report uses this to build the tree.
Parent-child relationships can cross repository boundaries (see grouping logic below).

**Archived items:** GitHub auto-archives closed project items after ~2 weeks. The default
`items` query does not return archived items (`filter:` argument does not exist in the
schema). Issues that are archived but have a matching workbench service are fetched
individually via the Issues API using `_fetch_issues_batch`; their estimate is taken from
`Service.effort_hours` (synced from the project board before archival).

### Workbench

- `Service` — linked to a GitHub issue URL via `external_reference` (exact match) or
  `description` (substring match, legacy fallback)
- `Service.external_reference` — always-editable URL field; set by `github_create_offer_issues`
- `Service.effort_hours` — synced from the GitHub `Estimate` field
- `Service.offer` — FK to `Offer`; `None` if not yet in any offer
- `Offer.status` — `ACCEPTED`, `DECLINED`, `REPLACED`, `SENT`, `IN_PREPARATION`
- `LoggedHours` — actual time tracked against a service

---

## Classification: Offered vs. Additional

### Primary mechanism: issue created from service

When an offer is accepted, the PM runs `github_create_offer_issues` to create one GitHub
issue per service. This issue is the anchor for that service on the board:
- Created in the appropriate repository
- Added to the project board automatically
- "Estimate" field set from `Service.effort_hours`
- Issue URL written back to `Service.external_reference` for matching

Team members then create sub-issues under the service issue for detailed work. The
**parent → child hierarchy expresses the billing structure**: an issue whose root ancestor
is a service issue linked to an accepted offer is classified as `angeboten`. A top-level
issue with no such ancestor is `zusätzlich`.

### Why labels alone don't work

- GitHub's audit log **does not expose project field change history.**
- Service descriptions on accepted offers are **read-only** — the URL-in-description
  matching strategy can't be applied retroactively.
- Labels require manual upkeep; the hierarchy is structural and emerges naturally.

### Labels as an override

The labels `angeboten` and `zusätzlich` are still used, but only as an **explicit override**
when the structural classification is wrong — e.g. an issue that grew beyond the scope of
its parent service should be labeled `zusätzlich` to signal additional billing, even though
it lives in the tree under a service issue.

| Structural classification | Label override | Final display |
|---|---|---|
| parent is accepted-offer service | — | `angeboten` |
| parent is accepted-offer service | `zusätzlich` | `zusätzlich` (override) |
| no service ancestor | — | `zusätzlich` |
| no service ancestor | `angeboten` | `angeboten (Angebot ausstehend)` |

### Service ↔ issue matching

Two mechanisms are used, in priority order:

1. **`Service.external_reference`** — exact URL match. Set by `github_create_offer_issues`
   when creating issues from services. Always editable regardless of offer status, so it can
   be updated even for services on accepted offers (where the description is read-only).
2. **URL in `Service.description`** — substring match of the GitHub issue URL. Legacy
   fallback for manually linked services and data predating `external_reference`.

For archived issues (auto-archived after ~2 weeks on the board), the report batch-fetches
them directly from the Issues API using URLs found in `external_reference` or descriptions.

---

## Report Structure

### XLSX output

Columns: `Repo`, `Issue`, `L1`–`L4` (tree depth), `Status`, `Billing`, `Label set by`,
`Label set at`, `Own est. (h)`, `Own logged (h)`, `Total est. (h)`, `Total logged (h)`,
`Delta (h)`, `Offer`, `Cross-app parent`.

- **Tree depth**: the issue title is placed in the column matching its depth (L1 = root,
  L2 = child, etc.) so the hierarchy is visible without cell indentation.
- **Own vs. Total**: `Own` columns show the issue's direct estimate/hours only. `Total`
  columns aggregate the issue and all its descendants. Grouping issues (Sammelticket)
  should not carry an estimate of their own to avoid double-counting.
- **Rollup rows**: each repo group ends with `Total Angeboten` and `Total Zusätzlich`
  summary rows (own values only, not double-counting children).
- **Unmatched services**: workbench services from projects that had at least one matched
  service, but which have no GitHub issue link, are appended after the tree in a separate
  section.

### Stdout output

Same data, printed as an indented tree with `[✓]`/`[ ]` state markers, `⚠ overrun` flags,
and per-repo `Angeboten`/`Zusätzlich` totals.

---

## Grouping Logic

**Billing unit = Django app, not repository.** A Django app may have issues spread across
many repositories. Cross-repo parent links *within* the same app group are legitimate cost
groupings and are followed normally. Cross-*app* parent links mix independent billing
streams and are excluded from rollup.

**Configuration:** `settings.GITHUB_APP_REPOS` maps app keys to lists of repo names:

```python
GITHUB_APP_REPOS = {
    "002": ["RepoA", "RepoB", "Betrieb", "Produktpflege", ...],
    "005": ["RepoC", ...],
}
```

**Grouping rules:**
1. Parent-child hierarchy is followed freely within an app group.
2. Cross-app parent links: the child is shown as a root in its own repo group, with the
   parent repo noted as a warning annotation.
3. Issues with no parent, or with a cross-app parent, are shown flat within their repo.

**GitHub Actions discouragement:** a workflow in the org-level `.github` repo posts a
warning comment when a parent is set that crosses app boundaries. Same-app cross-repo
links get no warning.

---

## Implementation

### Files

- `workbench/projects/github_cost_allocation.py` — core module:
  - `fetch_project_items(project_url)` — paginates the project board, builds `IssueNode`
    list, fetches billing label attribution.
  - `_fetch_archived(issues, github_services, ...)` — batch-fetches issues for unmatched
    services; appends them to the issue list with estimates from `Service.effort_hours`.
  - `_fetch_issues_batch(refs, headers)` — single aliased GraphQL query per repo for
    bulk issue fetching.
  - `build_tree(issues, app_repos)` — resolves parent-child links, groups into `RepoGroup`
    list.
  - `join_with_workbench(issues)` — matches issues to workbench services, fetches archived
    issues for unmatched services, returns unmatched services grouped by project.
  - `billing_classification(issue)` — derives display string from label + offer state.

- `workbench/management/commands/github_cost_allocation.py` — report command:
  - `--project-url` to override `settings.GITHUB_PROJECT_URLS[0]`
  - `--output FILE.xlsx` for XLSX output; defaults to stdout tree
  - `--mailto EMAIL[,EMAIL]` to send the XLSX by email

- `workbench/management/commands/github_create_offer_issues.py` — issue creation command:
  - `<offer_pk> --repo REPO_NAME` required arguments
  - Creates one GitHub issue per service, adds to project board, sets Workbench + Estimate fields
  - Writes issue URL back to `Service.description` for fallback matching
  - `--dry-run` to preview without API calls

- `github-actions/.github/workflows/` — org-level GitHub Actions:
  - `add-to-project.yml` — adds issues/PRs to the project board
  - `warn-cross-app-parent.yml` — posts comment on cross-app parent links
  - `sync-labels.yml` — reusable: syncs label set to a single repo
  - `sync-labels-all-repos.yml` — scheduled: syncs labels to all repos in `app-repos.json`
  - `caller-workflow-example.yml` — template for per-repo caller workflows

- `github-actions/config/app-repos.json` — app→repo mapping (mirrors `GITHUB_APP_REPOS`)
- `github-actions/config/labels.json` — canonical label definitions

### Settings

- `GITHUB_API_TOKEN` — personal access token
- `GITHUB_PROJECT_URLS` — list of project board URLs; first entry is used by default
- `GITHUB_APP_REPOS` — app→repo mapping for cross-app detection

---

## Open Questions

1. **GitHub Actions trigger for parent changes**: `issues: types: [sub_issue_added]` needs
   verification — it may not be available in GitHub Actions. Currently using `issues:
   types: [edited]` as best-effort. If unreliable, a scheduled workflow or GitHub App
   webhook would be needed.

2. **Multi-parent issues**: GitHub allows an issue to have multiple parents. Currently only
   `Issue.parent` (the direct parent) is used. Behaviour with multiple parents is untested.

3. **Overrun threshold**: currently flags exact overrun (`actual > estimate`). A 10% buffer
   threshold (`actual > estimate * 1.1`) could reduce noise — to be decided.

4. **HTML view**: not yet implemented. A collapsible tree in the project detail page would
   complement the XLSX for quick review without downloading a file.

5. **`ADD_TO_PROJECT_PAT` org secret**: needs to be created in GitHub for the
   `add-to-project.yml` workflow to function.
