"""API tokens"""

import click

from wb.core import (
    cli,
    console,
    current_installation,
    echo_json,
    forget_installation,
    make_table,
    request,
)


@cli.group(invoke_without_command=True)
@click.pass_context
def tokens(ctx):
    """List and revoke your API tokens, e.g. of computers you don't use
    anymore

    Without a command, lists the tokens. `wb logout` revokes the token wb
    uses."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_tokens)


def _date(value):
    return value[:10] if value else ""


@tokens.command("list")
@click.option("--json", "as_json", is_flag=True)
def list_tokens(as_json):
    """Your API tokens which haven't expired yet, the one wb uses is marked
    with *"""
    data = request("GET", "tokens/")
    if as_json:
        echo_json(data)
        return
    table = make_table("ID>", "Title", "Access", "Created", "Last used", "Expires")
    for token in data:
        table.add_row(
            f"{'*' if token['current'] else ''}{token['id']}",
            token["title"],
            token["access_label"],
            _date(token["created_at"]),
            _date(token["last_used_at"]),
            _date(token["expires_at"]),
        )
    console.print(table)


@tokens.command("delete")
@click.argument("token_ids", nargs=-1, type=int, required=True)
@click.option("--json", "as_json", is_flag=True)
def delete_tokens(token_ids, as_json):
    """Revoke API tokens immediately, by ID (see `wb tokens`)

    Revoking the token wb uses logs out like `wb logout`. Read only tokens
    may only revoke themselves."""
    # The token wb uses goes last, the others need it
    current = {token["id"] for token in request("GET", "tokens/") if token["current"]}
    deleted = []
    for token_id in sorted(set(token_ids), key=lambda token_id: token_id in current):
        token = request("DELETE", f"tokens/{token_id}/")
        deleted.append(token)
        message = f"Revoked {token['title']} ({token_id})."
        if token["current"]:
            forget_installation(url := current_installation())
            message = f"{message} Logged out from {url}."
        if not as_json:
            click.echo(message)
    if as_json:
        echo_json(deleted)
