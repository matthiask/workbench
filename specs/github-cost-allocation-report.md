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
| `Estimate` | Number | Hours estimate — synced to workbench `Service.effort_hours` |

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

- `Service` — linked to a GitHub issue URL via `description` (substring match)
- `Service.effort_hours` — synced from the GitHub `Estimate` field
- `Service.offer` — FK to `Offer`; `None` if not yet in any offer
- `Offer.status` — `ACCEPTED`, `DECLINED`, `REPLACED`, `SENT`, `IN_PREPARATION`
- `LoggedHours` — actual time tracked against a service

---

## Classification: Offered vs. Additional

### Why project board fields don't work

- GitHub's audit log **does not expose project field change history** — confirmed:
  `ProjectV2ItemFieldValueUpdatedAuditEntry` and `ProjectV2ItemFieldValueUpdatedEvent`
  do not exist in the schema.
- Offers are created early, often before GitHub issues exist; classification is decided later.
- The customer has GitHub access but no workbench access — they need to participate in
  classification, but a project field gives no attribution.

### Labels as the solution

**Issue labels are auditable.** The `LabeledEvent` in an issue's timeline records the actor
login and timestamp. This gives us attribution for free: we can see who applied the label
and when, whether that was a team member or the customer.

**Labels in use:**
- `angeboten` — covered by an existing offer
- `zusätzlich` — additional work, to be billed separately

### Integration with workbench

Labels are the input signal; workbench offer linkage is authoritative for billing.

| GitHub label | `Service.offer` status | Display |
|---|---|---|
| `angeboten` | `ACCEPTED` | `angeboten` |
| `angeboten` | other / None | `angeboten (Angebot ausstehend)` |
| (none) | `ACCEPTED` | `angeboten ⚠ label fehlt` |
| `zusätzlich` | any | `zusätzlich` |
| `zusätzlich` | `DECLINED` | `zusätzlich (Angebot abgelehnt)` |
| (none) | None | `—` |

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
  - `_fetch_issues_batch(refs, headers)` — batch-fetches issues not on the board (archived)
    via a single aliased GraphQL query grouped by repo.
  - `build_tree(issues, app_repos)` — resolves parent-child links, groups into `RepoGroup`
    list.
  - `join_with_workbench(issues)` — matches issues to workbench services, fetches archived
    issues for unmatched services, returns unmatched services grouped by project.
  - `billing_classification(issue)` — derives display string from label + offer state.

- `workbench/management/commands/github_cost_allocation.py` — management command:
  - `--project-url` to override `settings.GITHUB_PROJECT_URLS[0]`
  - `--output FILE.xlsx` for XLSX output; defaults to stdout tree

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
