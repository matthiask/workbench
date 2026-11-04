"""GitHub milestones linked to offers

Workbench stores the URLs of milestones as external references of offers and
doesn't talk to GitHub itself. These commands use the GitHub CLI `gh` for
GitHub and the API for Workbench."""

import json
import re
import subprocess

import click

from wb.core import (
    cli,
    console,
    echo_json,
    echo_offer,
    format_bool,
    link,
    make_table,
    request,
    terminate,
)


MILESTONE_URL = re.compile(
    r"^https://github\.com/(?P<repo>[\w.-]+/[\w.-]+)/milestone/(?P<number>\d+)/?$"
)
REPO = re.compile(r"^[\w.-]+/[\w.-]+$")


def gh(path, *, method="GET", fields=None, paginate=False):
    """Call the GitHub API through `gh api`"""
    args = ["gh", "api", "-X", method, path]
    if paginate:
        args.append("--paginate")
    for key, value in (fields or {}).items():
        args += ["-f", f"{key}={value}"]
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        terminate("The GitHub CLI `gh` is needed, see https://cli.github.com/")
    if result.returncode:
        terminate(f"GitHub: {result.stderr.strip() or result.stdout.strip()}")
    if not paginate:
        return json.loads(result.stdout)
    # --paginate concatenates the JSON arrays of the pages
    items, decoder, i, out = [], json.JSONDecoder(), 0, result.stdout
    while i < len(out):
        if out[i].isspace():
            i += 1
            continue
        page, i = decoder.raw_decode(out, i)
        items += page
    return items


def repository(value):
    if not REPO.match(value):
        raise click.BadParameter("Use OWNER/REPO, e.g. matthiask/workbench.")
    return value


def milestone_url(value):
    if not (match := MILESTONE_URL.match(value)):
        raise click.BadParameter(
            "Use the URL of the milestone, e.g."
            " https://github.com/OWNER/REPO/milestone/3"
        )
    return match


def fetch_milestone(match):
    return gh(f"repos/{match['repo']}/milestones/{match['number']}")


def linked_offers(url):
    params = {"external_reference": url, "limit": 100}
    return request("GET", "offers/", params=params)["items"]


def references(offer):
    return offer["external_reference"].split()


def add_reference(offer, url, *, dry_run):
    """Add the URL to the external references of the offer, keep the others"""
    if url in references(offer):
        return offer
    return request(
        "PATCH",
        f"offers/{offer['id']}/",
        params={"dry_run": format_bool(dry_run)},
        json={"external_reference": "\n".join([*references(offer), url])},
    )


def offer_line(offer):
    return f"Workbench: {offer['code']} {offer['url']}"


def describe_offer(milestone, offer, *, dry_run):
    """Add a link to the offer to the milestone's description, for people
    looking at GitHub"""
    description = milestone.get("description") or ""
    if dry_run:
        click.echo("Would link the offer in the milestone's description.", err=True)
        return
    if offer["url"] in description:
        return
    gh(
        f"repos/{milestone['_repo']}/milestones/{milestone['number']}",
        method="PATCH",
        fields={
            "description": "\n\n".join(filter(None, [description, offer_line(offer)]))
        },
    )


def echo_milestone(milestone, offers):
    console.print(
        link(f"{milestone['title']} ({milestone['state']})", milestone["html_url"]),
        style="bold",
    )
    for offer in offers:
        console.print(
            link(
                f"  {offer['code']} {offer['title']} ({offer['status']})", offer["url"]
            )
        )


def refuse_linked(url, offers, *, force):
    if offers and not force:
        codes = ", ".join(offer["code"] for offer in offers)
        terminate(
            f"{url} is already linked with {codes}. Every milestone should belong"
            " to one offer; pass --force to link it anyway."
        )


def dry_run_option(fn):
    return click.option(
        "--dry-run", is_flag=True, help="Show what would happen, change nothing."
    )(fn)


@cli.group()
def milestones():
    """GitHub milestones linked to offers

    The links are the milestone URLs in the external references of the
    offers. Needs the GitHub CLI `gh`."""


@milestones.command("list")
@click.argument("repos", nargs=-1, required=True, type=repository)
@click.option(
    "--state",
    type=click.Choice(["open", "closed", "all"]),
    default="all",
    show_default=True,
)
@click.option("--unlinked", is_flag=True, help="Only milestones without an offer.")
@click.option("--json", "as_json", is_flag=True)
def list_milestones(repos, state, unlinked, as_json):
    """Milestones of repositories (OWNER/REPO) and their offers"""
    rows = []
    for repo in repos:
        for milestone in gh(
            f"repos/{repo}/milestones?state={state}&per_page=100", paginate=True
        ):
            offers = linked_offers(milestone["html_url"])
            if unlinked and offers:
                continue
            rows.append({
                "repo": repo,
                "number": milestone["number"],
                "title": milestone["title"],
                "description": milestone["description"] or "",
                "state": milestone["state"],
                "open_issues": milestone["open_issues"],
                "closed_issues": milestone["closed_issues"],
                "url": milestone["html_url"],
                "offers": [
                    {
                        key: offer[key]
                        for key in ("id", "code", "title", "status", "url")
                    }
                    for offer in offers
                ],
            })
    if as_json:
        echo_json(rows)
        return
    if not rows:
        console.print("No milestones.")
        return
    table = make_table(
        "Repository", "#>", "Milestone", "State", "Open>", "Closed>", "Offers"
    )
    for row in rows:
        table.add_row(
            row["repo"],
            str(row["number"]),
            link(row["title"], row["url"]),
            row["state"],
            str(row["open_issues"]),
            str(row["closed_issues"]),
            ", ".join(offer["code"] for offer in row["offers"]) or "—",
        )
    console.print(table)


@milestones.command()
@click.argument("offer_id", type=int)
@click.argument("repo", type=repository)
@click.option("--title", help="Defaults to the last part of the offer's title.")
@dry_run_option
def create(offer_id, repo, title, dry_run):
    """Create a milestone in REPO (OWNER/REPO) for an offer and link them"""
    offer = request("GET", f"offers/{offer_id}/")
    title = title or offer["title"].rsplit(" | ", 1)[-1]
    existing = [
        milestone
        for milestone in gh(
            f"repos/{repo}/milestones?state=all&per_page=100", paginate=True
        )
        if milestone["title"] == title
    ]
    if existing:
        terminate(
            f"{repo} already has the milestone {title!r}: {existing[0]['html_url']}"
            "\nUse `wb milestones link` to link it."
        )
    if dry_run:
        click.echo(f"Would create the milestone {title!r} in {repo}.", err=True)
        click.echo(f"Would add its URL to the references of {offer['code']}.", err=True)
        return
    milestone = gh(
        f"repos/{repo}/milestones",
        method="POST",
        fields={"title": title, "description": offer_line(offer)},
    )
    offer = add_reference(offer, milestone["html_url"], dry_run=False)
    echo_milestone(milestone, [offer])


@milestones.command("link")
@click.argument("offer_id", type=int)
@click.argument("url", type=milestone_url)
@click.option("--force", is_flag=True, help="Also if other offers are linked.")
@dry_run_option
def link_milestone(offer_id, url, force, dry_run):
    """Link an existing milestone (its URL) with an offer"""
    milestone = fetch_milestone(url) | {"_repo": url["repo"]}
    offer = request("GET", f"offers/{offer_id}/")
    others = [o for o in linked_offers(milestone["html_url"]) if o["id"] != offer_id]
    refuse_linked(milestone["html_url"], others, force=force)
    offer = add_reference(offer, milestone["html_url"], dry_run=dry_run)
    describe_offer(milestone, offer, dry_run=dry_run)
    echo_milestone(milestone, [*others, offer])


@milestones.command("offer")
@click.argument("project_id", type=int)
@click.argument("url", type=milestone_url)
@click.option(
    "--title",
    help='Defaults to "PROJECT TITLE | MILESTONE TITLE", like other offers.',
)
@click.option("--force", is_flag=True, help="Also if other offers are linked.")
@dry_run_option
def create_offer(project_id, url, title, force, dry_run):
    """Create a service group for an existing milestone (its URL)

    The service group has no services yet and is linked with the milestone."""
    milestone = fetch_milestone(url) | {"_repo": url["repo"]}
    refuse_linked(
        milestone["html_url"], linked_offers(milestone["html_url"]), force=force
    )
    if not title:
        project = request("GET", f"projects/{project_id}/")
        title = f"{project['title']} | {milestone['title']}"
    offer = request(
        "POST",
        f"projects/{project_id}/offers/",
        params={"dry_run": format_bool(dry_run)},
        json={
            "title": title,
            "description": milestone.get("description") or "",
            "status": "service_group",
            "external_reference": milestone["html_url"],
        },
    )
    echo_offer(offer)
    describe_offer(milestone, offer, dry_run=dry_run)
    if dry_run:
        click.secho("Dry run, nothing has been saved.", fg="yellow", err=True)
