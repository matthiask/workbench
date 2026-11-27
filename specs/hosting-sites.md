# Spec: Hosted sites

## Goal

Basecamp to-do "Hosting Kontakt in Workbench hinterlegen können" (November
2026). Today a Google spreadsheet lists the hosted sites and their
contacts; nobody opens it when something changes, so it's rarely up to
date. Wanted:

- Know whether a recurring invoice exists for each site running on one of
  our servers.
- Know whom to contact about an outage or a maintenance window.
- The contacts of each server (classic servers and a Kubernetes cluster), to
  write to them all at once.
- The contact for IT concerns (DNS records etc.) when those are handled
  elsewhere, and a link to the credentials in the password manager.

## Decisions

- **The site is the unit**, not the organization or the contact person. A
  customer may have several sites (on different servers), sites move
  between servers, the people of an organization change. Notes on the
  organization went stale at once, a group per server would have to be
  edited for every move.
- **Contacts of a server are computed** from its sites, never maintained
  as a group.
- **Two contact roles**: outage / maintenance, IT (DNS etc.). We only host
  sites we developed, no external developers to contact.
- **Recurring invoices point to their site** (`RecurringInvoice.site`,
  optional). A site may have several recurring invoices (e.g. a second
  vhost, another periodicity): adding one doesn't change the existing one.
- **A skill keeps the list of sites current** (`wb` and `kubectl` with the
  rights of the person running it): no service, no token in the cluster,
  no copy of personal data elsewhere. A scheduled to-do in Biwak reminds
  us to run it. Recurring invoices stay managed by hand; the skill reports
  sites without one.
- **Credentials stay in the password manager**, Workbench only stores a
  link to the entry.
- **Feature `HOSTING`**, only for Feinheit for now (`F.ALWAYS` there,
  `F.NEVER` elsewhere). The installations share code and schema, the
  tables exist everywhere; views, navigation, API and the fields on other
  pages (recurring invoice form, organization, person) require the
  feature.

## 1. Model (`workbench/hosting/`)

```
Server      title (unique), notes, is_archived
Site        title (the main domain), domains (further host names, one per
            line), server → Server (PROTECT), customer → Organization
            (PROTECT), owned_by → User (who knows the site best),
            password_manager_url, no_invoice_reason, notes, is_archived
SiteContact site → Site (CASCADE), person → Person (CASCADE),
            role (outage | it); unique (site, person, role)
RecurringInvoice.site → Site (SET_NULL, optional)
```

- `Site.host_names()`: title and domains, lowercased, for matching
  ingresses and vhosts.
- `no_invoice_reason`: free text ("maintenance contract", "internal",
  "included in the mandate").
- Archiving a site keeps its history; archived sites have no problems and
  don't count for their server's contacts.
- Contacts: merging people (`workbench/contacts/merge.py`) moves their site
  contacts; site contacts count as use for `archive_unused_contacts()`
  (`_recent()`).
- Audit log: the new tables get entries in `prune_audit()` and `HISTORY`.

## 2. Problems

An active site (not archived) has a problem when:

- it has no running recurring invoice (not ended: `ends_on` empty or in
  the future) and no `no_invoice_reason`,
- it has no active outage contact (archived people don't count).

The site list filters by server and by "with problems"; the site and
server pages show them.

## 3. Web interface

- **Sites** list (`.wb-row`): title, server, customer, problems as badges.
  Filters: server, problems, archived.
- **Site** page: fields, contacts by role (person, organization, email,
  phone), recurring invoices (title, periodicity, ends on; only with
  `CONTROLLING`), link to the password manager, notes.
- **Server** page: its active sites, and the outage contacts of all of
  them with their email addresses, copyable as one list (for a BCC).
- Organization, person and recurring invoice pages list their sites.
- The recurring invoice form gets the site field (sites of the customer).

## 4. API and `wb`

- `/api/hosting/servers/`, `/api/hosting/sites/` (search: server,
  customer, problems, include archived), show, create, update; site
  contacts as part of the site (add / remove).
- `wb servers`, `wb sites search|show|create|update`,
  `wb sites contacts add|remove`.
- Recurring invoices in the API get `site` (ID).

## 5. Skill `workbench-hosting`

Run every few months (Biwak to-do) or before a maintenance window:

1. Collect what runs: the ingresses of the clusters (`kubectl`), the vhosts
   of the classic servers. The server's notes in Workbench say how (command,
   kube context, host names to leave out), so this knowledge stays internal
   and the public skill stays generic; the skill proposes adding it when
   missing.
2. Compare with `wb sites search --server …` by host name.
3. Report and, after confirmation, fix: running sites missing in Workbench
   (create them, find the customer), sites in Workbench which don't run
   anymore (archive; mention their recurring invoices), sites with
   problems (no invoice and no reason, no outage contact).
4. "Whom do I write to when a server has a problem?": the server's
   outage contacts.

The initial import uses the same skill: recurring invoices with the domain
in their title, the vhosts and the Google spreadsheet, reviewed by hand.
