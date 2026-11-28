# Contacts

"Contacts" holds people, organizations and groups. Customers are always
organizations; for a private person create an organization and tick
"is private person", which leaves its name out of addresses.
<kbd>Ctrl-Shift-C</kbd> jumps to a person.

## Organizations and people

- An organization's **central email address** (e.g. info@) and **phone
  number** (the reception) belong to the organization; its people show
  them too, don't add them to the people.
- A person's phone numbers, email addresses and postal addresses can be
  added once the person has been saved. "Copy from colleague" takes over
  a colleague's address. A "Home" address leaves out the organization.
  An email address which another person or an organization (as its
  central address) uses already is a warning; a person has each address
  only once.
- The **job title** (e.g. Head of Communications) belongs to the person,
  not into the address: addresses print without it.
- Addresses print in the order of Swiss Post: the **address suffix**
  (c/o, a department, a building) above the street, the **post office
  box** below it. Street and post office box are optional,
  some small organizations only have a postal code and a city. The override replaces the whole address, organization and name
  included; only use it when the fields can't express the address.
- When an organization moves, "Change" on one of its addresses changes
  it for the selected people at once.
- When someone changes jobs and has projects, deals or invoices, archive
  the person and create a new one at the new organization rather than
  changing the organization.

## Groups

Groups collect contacts, e.g. for mailings. Groups which **apply to
organizations** (e.g. industries) belong to the organization: ticking
such a group on a person adds the whole organization. Pinned groups are
listed first. "Missing or incomplete postal address" finds the people
who can't get a letter yet, also those whose address doesn't print well
(line breaks in fields, placeholders like "-" instead of a street, a
whole address in the organization's name, an address suffix repeating
the organization); check the group before a mailing. The people list
filtered by a group exports the people as
XLSX or vCards. The XLSX has the complete postal address in one cell,
as printed on invoices, ready for letters and labels; the address
fields follow for sorting and filtering.

## Duplicates, archiving, deleting

- **Merge** duplicates instead of deleting them: "Merge into another
  person" (or organization) moves projects, deals, invoices, contact
  details and groups to the contact kept. "Possible duplicates" on the
  lists and on people finds candidates.
- **Archive** contacts which aren't needed anymore: they stay with their
  history but aren't offered for new projects, deals and invoices.
  Archiving an organization offers to archive its people; archiving its
  last person archives the organization too, unless it has open projects
  or deals, active sites or running recurring invoices.
- Contacts unused for five years are archived automatically.
- Organizations with related records (people, projects, invoices and
  so on) can't be deleted: merge or archive them.

## Sites

Installations which host websites list them under "Sites" (only if the
hosting feature is enabled). A site is one website on one server, with
its customer, further domains, the person at our end who knows it best
and a link to its credentials in the password manager (never the
credentials themselves).

- **Contacts** of a site: whom to inform about **outages and
  maintenance**, and whom to ask about **IT** matters like DNS records,
  e.g. at the customer's IT provider. Merging people moves their site
  contacts; deleting a person who is a site contact is a warning.
- **Recurring invoices** name their site; a site may have several (e.g.
  another periodicity). "Recurring invoice" on the site creates one for
  it.
- Active sites without a running recurring invoice (and without a reason
  why there's none, e.g. a maintenance contract) or without a contact for
  outages are listed under "With problems".
- A **server** lists the outage contacts of all its active sites with
  their email addresses, to copy them for a mail about a maintenance
  window. Moving a site to another server only changes its server. Its
  notes say how to list the sites running on it (command, where to run
  it), never credentials.
- Archive sites which don't run anymore instead of deleting them, and end
  their recurring invoices.
