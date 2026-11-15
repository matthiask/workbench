"""Claude Code skills using wb, linked into Claude Code's skills

The skills are the directories next to this file. Links point to them
where wb is installed: the checkout for editable installs, else uv's
environment of the tool, so that upgrading wb upgrades them too."""

import os
from pathlib import Path

import click
import yaml

from wb.core import cli, console, echo_json, make_table


SKILLS = Path(__file__).parent


def _skills():
    return sorted(path.parent for path in SKILLS.glob("*/SKILL.md"))


def _target(project):
    if project:
        return Path.cwd() / ".claude" / "skills"
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(config) if config else Path.home() / ".claude") / "skills"


def _description(skill):
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---")[1])["description"]


def _ours(link):
    """Links to skills of a wb, this one or another (an earlier
    environment, a checkout)"""
    if not link.is_symlink():
        return False
    target = Path(os.readlink(link))
    return target.parent.name == "skills" and target.parent.parent.name == "wb"


def _state(link, skill):
    if link.is_symlink():
        if Path(os.readlink(link)) == skill:
            return "linked"
        return f"linked to {os.readlink(link)}"
    if link.exists():
        return "a directory of its own"
    return "not linked"


project_option = click.option(
    "--project",
    is_flag=True,
    help="The skills of the project in this directory (.claude/skills), "
    "not your personal ones.",
)


@cli.group()
def skills():
    """Claude Code skills using wb"""


@skills.command("list")
@project_option
@click.option("--json", "as_json", is_flag=True)
def list_(project, as_json):
    """The skills and whether Claude Code has them"""
    target = _target(project)
    data = [
        {
            "name": skill.name,
            "description": _description(skill),
            "path": str(skill),
            "state": _state(target / skill.name, skill),
        }
        for skill in _skills()
    ]
    if as_json:
        echo_json(data)
        return
    table = make_table("Skill", "State", "Description")
    # Only the descriptions wrap
    table.columns[0].no_wrap = table.columns[1].no_wrap = True
    for row in data:
        table.add_row(row["name"], row["state"], row["description"])
    console.print(table)
    if any(row["state"] != "linked" for row in data):
        console.print(f"Link them with wb skills install{' --project' * project}.")


@skills.command()
@project_option
def install(project):
    """Link the skills into Claude Code's skills, again when wb brings new
    ones (upgrading wb updates those linked)"""
    target = _target(project)
    target.mkdir(parents=True, exist_ok=True)
    names = set()
    for skill in _skills():
        names.add(skill.name)
        link = target / skill.name
        if link.exists() and not link.is_symlink():
            console.print(f"{link} is a directory of its own, left alone.")
            continue
        if link.is_symlink() and Path(os.readlink(link)) == skill:
            continue
        link.unlink(missing_ok=True)
        link.symlink_to(skill, target_is_directory=True)
        console.print(f"Linked {skill.name}.")
    # Skills wb doesn't have anymore, or links to an environment uv removed
    for link in sorted(target.iterdir()):
        if link.name not in names and _ours(link):
            link.unlink()
            console.print(f"Removed {link.name}.")
    console.print(f"The skills are in {target}.")


@skills.command()
@project_option
def uninstall(project):
    """Remove the links to the skills"""
    target = _target(project)
    if target.is_dir():
        for link in sorted(target.iterdir()):
            if _ours(link):
                link.unlink()
                console.print(f"Removed {link.name}.")
