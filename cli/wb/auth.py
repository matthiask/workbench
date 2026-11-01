"""Logging in, installations and shell completion"""

import click
from click.shell_completion import (
    BashComplete,
    FishComplete,
    ZshComplete,
    add_completion_class,
    get_completion_class,
)

from wb import core
from wb.core import (
    browser_login,
    cli,
    complete_installations,
    console,
    echo_deal_list,
    echo_fields,
    echo_invoice_list,
    echo_json,
    echo_offer_list,
    find_installation,
    installation_url,
    link,
    make_table,
    read_config,
    request,
    save_config,
    terminate,
    write_config,
)


@cli.command()
@click.argument("url", required=False)
@click.option(
    "--token",
    "paste_token",
    is_flag=True,
    help="Paste a token from the API tokens page instead of using the browser.",
)
@click.option(
    "--read",
    "access",
    flag_value="read",
    help="wb may only read, e.g. for tools which shouldn't change anything.",
)
@click.option(
    "--write",
    "access",
    flag_value="write",
    help="wb may read and write, e.g. create offers and close deals.",
)
def login(url, paste_token, access):
    """Authorize wb to access Workbench in your name

    Opens the browser; the URL defaults to the current installation. Choose
    the access explicitly with --read or --write. Logging in to another
    installation adds it and makes it the current one (see `wb auth`). Use
    --token on computers without a browser, the token's access is chosen when
    creating it."""
    if not (url := url or read_config()["current"]):
        terminate("Which Workbench? Run `wb login URL --read` or `--write`.")
    url = installation_url(url)
    if paste_token:
        save_config(url, click.prompt("API token", hide_input=True).strip())
        click.echo(f"Saved {core.CONFIG}")
    elif not access:
        terminate("Choose the access: `wb login --read` or `wb login --write`.")
    else:
        browser_login(url, access)


class _CompleteOptions:
    """Offer the options when there's nothing else to complete, Click only
    does this when a dash has been typed"""

    def get_completions(self, args, incomplete):
        completions = super().get_completions(args, incomplete)
        # After an option its value may be expected, e.g. an ID
        if not (completions or incomplete or (args and args[-1].startswith("-"))):
            completions = super().get_completions(args, "-")
        return completions


for _shell, _class in [
    ("bash", BashComplete),
    ("zsh", ZshComplete),
    ("fish", FishComplete),
]:
    add_completion_class(type(_class.__name__, (_CompleteOptions, _class), {}), _shell)


@cli.command()
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completion(shell):
    """Print the script which completes wb's commands in your shell

    bash: echo 'eval "$(wb completion bash)"' >> ~/.bashrc

    zsh: echo 'eval "$(wb completion zsh)"' >> ~/.zshrc

    fish: wb completion fish > ~/.config/fish/completions/wb.fish"""
    complete = get_completion_class(shell)(cli, {}, "wb", "_WB_COMPLETE")
    click.echo(complete.source())


@cli.group(invoke_without_command=True)
@click.pass_context
def auth(ctx):
    """Switch between the Workbench installations you're logged in to

    `wb login URL` adds installations. Switching affects all terminals;
    setting WORKBENCH_URL uses another installation in one terminal only,
    `wb -i NAME` for a single command.

    Without a command, lists the installations."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_installations)


@auth.command("list")
def list_installations():
    """List the installations, the current one is marked with *"""
    config = read_config()
    if not config["installations"]:
        terminate("Not configured yet. Run `wb login URL` first.")
    for url, installation in sorted(config["installations"].items()):
        access = installation.get("access")
        click.echo(
            f"{'*' if url == config['current'] else ' '} {url}"
            + (f" ({access})" if access else "")
        )


@auth.command("switch")
@click.argument("name", shell_complete=complete_installations)
def switch_installation(name):
    """Use another installation, NAME is any unique part of its URL"""
    url = find_installation(name)
    config = read_config()
    config["current"] = url
    write_config(config)
    click.echo(f"Using {url}")


@cli.command()
@click.option("--json", "as_json", is_flag=True)
def me(as_json):
    """Who you are and what's on your plate: projects, this week's planning,
    offers, invoices and deals which may need action"""
    user = request("GET", "me/")
    data = request("GET", "me/overview/")
    if as_json:
        echo_json({"user": user} | data)
        return

    echo_fields(
        user["full_name"],
        [
            ("Short name", user["short_name"]),
            ("Email", user["email"]),
            ("Workbench", user["url"]),
            ("Access", "read only" if user["access"] == "read" else "read and write"),
        ],
        url=user["url"],
    )
    table = make_table("ID>", "Code", "Title", "Customer", title="Your open projects")
    for project in data["projects"]:
        table.add_row(
            link(project["id"], project["url"]),
            link(project["code"], project["url"]),
            project["title"],
            link(project["customer"]["name"], project["customer"]["url"]),
        )
    console.print(table)

    table = make_table(
        "Project",
        "Planned work",
        "Hours>",
        "Provisional",
        title=f"Week of {data['week']}",
    )
    for pw in data["planned_work"]:
        project = pw["project"]
        table.add_row(
            link(f"{project['code']} {project['title']}", project["url"]),
            pw["title"],
            pw["hours"],
            "yes" if pw["is_provisional"] else "",
        )
    console.print(table)

    if data["offers"] is not None:
        echo_offer_list(data["offers"], title="Offers")
    if data["invoices"] is not None:
        echo_invoice_list(data["invoices"])
    if data["deals"] is not None:
        echo_deal_list(data["deals"], title="Deals")
