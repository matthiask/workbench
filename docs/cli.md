# Command line and API tokens

`wb` is Workbench's command line tool: it searches, shows and changes
projects, offers, invoices, deals, contacts, logged hours and costs,
absences and planning, and prints the reports. Assistants such as Claude Code use it too.

## Installing

"API tokens" in the menu with your name shows the commands for your
Workbench:

```
uv tool install "git+https://github.com/matthiask/workbench#subdirectory=cli"
wb login https://workbench.example.com/ --read
```

`wb login` opens the browser, where you authorize `wb` on this computer.
Choose `--read` (read only) or `--write` (read and write); read access
is enough for tools and assistants which only answer questions. Only
continue in the browser if you just started `wb` yourself. `wb me` shows
who you're logged in as.

When Workbench needs a newer `wb`, it says so and prints the upgrade
command (`uv tool upgrade --python … workbench-cli`).

`wb skills install` installs the skills for Claude Code which come with
`wb` (writing offers, logging hours, adding contacts, planning,
controlling and more). Run it again after upgrades which bring new
skills.

## Using wb

Commands follow `wb <noun> <verb>`, e.g. `wb projects search`,
`wb offers show 1234`, `wb deals update`. `wb --help` and
`wb <noun> --help` list everything. Most commands accept `--json`, and
changes `--dry-run`.

Changes are checked like in the web interface. Where the web interface
shows a warning, `wb` stops and prints the warning's code;
`--ignore-warning CODE` accepts it after you've checked.

`wb hours create SERVICE HOURS DESCRIPTION` and `wb costs create`
[log hours and costs](hours.md) with the checks and warnings of the
logbook form, `update` and `delete` change and remove them like in the
web interface. `wb services search --project ID` finds the service.
`wb timestamps start` and `wb timestamps stop` set
[timestamps](hours.md#timestamps).

## API tokens

`wb login` creates its token itself. On computers without a browser,
create a token on the "API tokens" page and use `wb login URL --token`.

- A token acts in your name, with your access: read only or read and
  write. The history of changes made with it lists your name; the
  administration's audit log also shows the token.
- It's shown once only, copy it right away.
- It expires 30 days after its last use; each use extends it.
- The bin icon revokes it immediately, so does `wb tokens delete ID`
  (`wb tokens` lists your tokens). `wb logout` revokes the token `wb`
  uses on this computer. Tokens of people who left stop working.
