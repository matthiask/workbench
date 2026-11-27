---
name: workbench-hosting
description: Keep the hosted sites in Workbench current with the `wb` CLI, compared with what actually runs on the servers (Kubernetes ingresses, vhosts), and find whom to contact about an outage or a maintenance window. Finds running sites missing in Workbench, sites which don't run anymore, sites without recurring invoice or without contact for outages, and UptimeRobot monitors missing or left over. Use when the user wants to update, check or import the list of sites or hosting customers, asks which sites run on a server, which sites have no recurring invoice, whom to inform about an outage or maintenance of a server, or wants to update the uptime monitors.
---

# Hosted sites in Workbench

The `wb` CLI talks to Workbench (see `wb --help`). If `wb` isn't installed or
configured, tell the user to run
`uv tool install "git+https://github.com/matthiask/workbench#subdirectory=cli"`
and `wb login URL --write`. Writing needs `--write`; if `wb` answers that the
token only allows reading, ask the user to log in with `--write` instead of
working around it. Sites need the hosting feature; without it `wb` answers
403, tell the user.

Propose, people decide. Collect, compare, then show the user what you'd
change as tables grouped by kind of finding. Validate every change with
`--dry-run` and only write after the user explicitly approves. Never
archive a site, end a recurring invoice or remove a contact on a guess.

A site is one website on one server: its main domain is the title, further
host names are its domains, it has a customer (organization), the person
at our end who knows it best (`owned_by`), contacts with a role (`outage`:
outages and maintenance, `it`: IT matters like DNS records, e.g. at the
customer's IT provider) and optionally a link to its entry in the password
manager (never the credentials themselves). Recurring invoices point to
their site, a site may have several.

    wb servers                          # the servers
    wb sites                            # active sites with problems
    wb sites search --server SERVER --csv
    wb sites show SITE                  # ID or title

## Whom to contact about a server

For an outage or a maintenance window:

    wb servers show SERVER              # outage contacts with their sites
    wb servers show SERVER --emails     # comma separated, for BCC

Mention contacts without email address and active sites without outage
contact (`wb sites search --server SERVER --problems`): they won't get the
mail. Draft the mail only if asked; don't send anything yourself.

## Updating the list of sites

Run it every few months (there may be a recurring to-do for it) or before a
migration. Ask which servers to check, all by default (`wb servers`).

### 1. Collect what runs

Each server's notes say how to list its sites (`wb servers show SERVER`):
the command, where to run it, the kube context, which host names to leave
out. Follow them, with the user's own access; ask before running anything
on a server and let the user run commands needing other credentials
themselves. Typical sources:

- Kubernetes clusters: `kubectl get ingress --all-namespaces -o json` in
  the cluster's context. Group the ingresses into sites, e.g. by the label
  of the deployment tool or by their name; skip system namespaces.
- Servers with vhosts: a command listing the domains and aliases per vhost,
  its output or a file from the user. Leave out the server's own technical
  host names.

If the notes don't say how, ask the user, and once it worked propose adding
it to the notes so the next run (and everybody else) finds it there:

    wb servers update SERVER --notes - < notes.md --dry-run

`--notes` replaces the notes: start from the current ones. Notes are for
how to get at the list, never credentials.

Host names only in our own zones (staging and preview domains) usually
aren't customer sites; list them separately and ask.

### 2. Compare

    wb sites search --server SERVER --include-archived --csv

The CSV has the host names (title and domains) of each site. Match running
sites to Workbench sites by host name, lowercased and ignoring a leading
`www.`. Group the findings:

1. **Running, not in Workbench**: propose a site per running site, with the
   main domain as title and the other host names as domains. Find the
   customer with `wb organizations search` and the recurring invoices with
   `wb recurring-invoices search DOMAIN --include-closed` (the domain is
   often in the title or description); their customer is the site's
   customer.
2. **In Workbench, not running anymore**: propose archiving the site
   (`wb sites update SITE --archived`). Show its recurring invoices: ending
   them is the user's decision, ask before
   `wb recurring-invoices update ID --ends-on DATE`.
3. **Moved**: the host names run on another server than recorded; propose
   `wb sites update SITE --server OTHER`.
4. **Host names changed**: propose the new domains (`--domain` replaces all
   further domains, `--no-domains` removes them).
5. **Archived in Workbench, but running**: ask; maybe unarchive it
   (`--not-archived`).

### 3. Problems

    wb sites search --problems

- **No recurring invoice**: search for one (`wb recurring-invoices search
  DOMAIN --include-closed`, `--customer ID`). If one exists, link it:
  `wb recurring-invoices update ID --site SITE_ID --dry-run`. If there is
  none, ask: is hosting included elsewhere (maintenance contract, mandate,
  internal site)? Then record the reason with
  `wb sites update SITE --no-invoice-reason "…"`. Otherwise it's hosting
  nobody invoices: list it for the user; creating a recurring invoice
  (amount, periodicity) is their decision. Once they've decided, propose
  `wb recurring-invoices create --site SITE_ID --contact ID --periodicity
  yearly --subtotal AMOUNT --third-party-costs 0 --dry-run`.
- **No contact for outages**: propose people, e.g. the contact of the
  recurring invoice or of the customer's recent projects
  (`wb organizations show ID`, `wb people search --organization ID`), and
  ask; the person receiving invoices isn't necessarily the right one.
  `wb sites contacts add SITE PERSON_ID --dry-run`. Create missing people
  with the workbench-contact skill.
- **Contact with the wrong role**: `wb sites contacts update SITE
  CONTACT_ID --role it --dry-run` (the contact ID is in `wb sites show`).
- **Duplicates**: a site created twice by mistake is deleted (`wb sites
  delete SITE --dry-run`); sites which ran once are archived instead.

### 4. Uptime monitors

If the sites are monitored with UptimeRobot (ask if unsure), every active
site should have a monitor and archived or removed sites shouldn't. This
needs the account's main API key in `UPTIMEROBOT_API_KEY`; if it isn't
set, ask the user to export it. Never ask them to paste it into the chat,
never print it. Use the v2 API with form-encoded POSTs:

    curl -s https://api.uptimerobot.com/v2/getMonitors \
        -d api_key="$UPTIMEROBOT_API_KEY" -d format=json \
        -d alert_contacts=1 -d limit=50 -d offset=0

`limit` is at most 50; page with `offset` until `pagination.total`. Match
monitors to sites by the host name in the monitor's `url`, lowercased and
ignoring a leading `www.`, against the title and domains of each site, as
in step 2 and taking the changes from steps 2 and 3 into account. Group
the findings:

1. **Active site without monitor**: propose a monitor on `https://TITLE/`
   with the site title as friendly name, and the alert contacts and
   threshold (alert delay) most other monitors use:

       curl -s https://api.uptimerobot.com/v2/newMonitor \
           -d api_key="$UPTIMEROBOT_API_KEY" -d format=json \
           -d type=1 -d url=https://www.beispiel.ch/ \
           -d friendly_name=www.beispiel.ch \
           -d alert_contacts=ID_THRESHOLD_RECURRENCE

   Several contacts are joined with `-`. Don't leave out the threshold:
   without one, UptimeRobot mails on the first failed check, so every
   short network interruption causes a flood of mails.

   Check what the URL answers first (`curl -s -o /dev/null -w
   '%{http_code}'`): a monitor on a site that answers 401 or 403 is down
   from the start. A 401 (password-protected, e.g. not live yet) gets a
   monitor with the basic auth credentials (`-d http_auth_type=1
   -d http_username=… -d http_password=…`), which the user takes from
   the password manager and exports themselves, never pasted into the
   chat; without them, skip the site. A 403 or another error: ask.
   Watch out for host names served by the server's default vhost (wrong
   certificate, e.g. `CN=feinheit06.nine.ch`): they answer 200, but
   nothing runs there.
2. **Monitor for an archived site or a host name nothing runs on**:
   propose deleting it (`deleteMonitor` with `-d id=ID`).
3. **Monitor URL not on the site's host names anymore** (e.g. after the
   host names changed): propose updating it (`editMonitor` with
   `-d id=ID -d url=...`).
4. **Monitors without alert contacts or without threshold**: list them;
   the first never alert, the second alert on every blip.

Monitors for things that aren't sites (the servers themselves, mail,
status endpoints) don't match any site: list them separately and leave
them alone. Changing monitors needs the user's approval like the
Workbench changes; the API has no dry run, so show the exact parameters
instead.

### 5. Write

After the user approved, apply the changes one by one without `--dry-run`:

    wb sites create --title www.beispiel.ch --domain beispiel.ch \
        --server SERVER --customer 345 --dry-run
    wb sites contacts add www.beispiel.ch 678 --role outage --dry-run
    wb sites contacts add www.beispiel.ch 679 --role it --dry-run

then the approved monitor changes, checking each API answer for
`"stat": "ok"`.

Finish with a short summary: what was created, changed and archived, which
monitors were added, changed or removed, and what's left for the user
(sites nobody invoices, missing contacts, invoices to end).
