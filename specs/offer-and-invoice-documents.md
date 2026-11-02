# Spec: Reworking offer and invoice documents

## Goal

Offers should be able to explain themselves. Today an offer is a flat list of
services below an optional intro text; whenever the scope needs some structure
we send a presentation along to explain it. People asked for section headings
with some body text between the services (Basecamp to-do "Zwischentitel und
Zwischen-Fliesstext für Workbench-Offerten", March 2024), and later for the
logo on offers and invoices.

Instead of bolting this onto the current reportlab code, this spec proposes
to render offers and invoices from HTML templates with WeasyPrint, with
descriptions in Markdown and a structure for offers (sections).

The layout of all documents will change a lot, old ones included. That's
accepted. The content of old documents must not change.

## 1. Today

### Rendering

All PDFs are built with reportlab through `pdfdocument`, in
`workbench/tools/pdf.py` (`PDFDocument`, about 850 lines):

- `process_offer()` and `process_invoice()` render one document each;
  `offers_pdf()` renders a cover letter plus all offers of a project,
  `dunning_letter()` a reminder letter plus the overdue invoices.
- Layout is done in code: fixed frames for the address window and the rest of
  the first page, a full frame for later pages, a frame for the QR bill.
  Column widths, paddings and lines are tuples of reportlab table styles.
- Stationery (logo or company name, footer address, page numbers) is drawn
  onto the canvas in `stationery()`. The logo is a PNG configured with
  `PDF_LOGO_SETTINGS`; only one namespace has one.
- Text is plain text. Descriptions are passed through `self.p()`; only the
  dunning letter uses `mini_html()`. There is no bold, no list, no heading
  inside a description.
- The QR bill is generated as SVG by `qrbill`, converted with `svglib` and
  appended as a drawing on its own page template.
- Texts which differ between namespaces (terms, agreement, payment
  instructions, credit text, VAT number, address) are settings in
  `settings.WORKBENCH`.

### When PDFs are generated

PDFs are never stored. They are generated on every request:

- `OfferPDFView`, `ProjectOfferPDFView`
- `InvoicePDFView`, the PDF export of the invoice list
- `dunning_letter()` and `SendReminderForm.process()` (attached to the
  reminder mail)
- `paid_debtors_zip()` in `workbench/credit_control/reporting.py`, the yearly
  export for bookkeeping, which regenerates every invoice of the period

So every change to `pdf.py`, to a setting like `PDF_ADDRESS` or
`PDF_INVOICE_PAYMENT`, or to a related object (the owner's name in "Our
reference") already changes documents which were sent years ago.

### Other users of `PDFDocument`

Not offers or invoices, internal only, out of scope here and can stay on
reportlab for now:

- annual working time and user statistics (`workbench/awt/pdf.py`)
- expense reports (`workbench/expenses/views.py`)

## 2. Old documents

Old offers and invoices are rendered with the new layout and the new
renderer, like everything else. Their content stays the same: their
descriptions are rendered as Markdown, and the texts which would change
their meaning are reviewed and escaped before the switch (section 4). That's the same situation as today, where every
change to `pdf.py` or to the settings already changes old documents; it
hasn't been a problem in practice (the bank account changed once in 20
years).

Not part of this rework, but possible later if it turns out to matter:
storing the PDF when an offer is offered or an invoice is sent (a small
`Document` model with a `FileField`), and serving the stored file afterwards.

## 3. Rendering with WeasyPrint

### Why

- Layout in HTML and CSS instead of frames, column tuples and table styles.
  Changing a margin or adding the logo is a CSS change.
- CSS paged media: `@page` rules with margin boxes for the footer and page
  numbers (`counter(page)` and `counter(pages)`, so "Seite 2 von 3"), a
  different first page (`@page :first`) for the address window, named pages
  for the QR bill.
- Table headers repeat on every page (`<thead>`), rows don't break in the
  middle (`break-inside: avoid`), headings stay with the following content
  (`break-after: avoid`). Today a service's title can end up at the bottom
  of a page with its description on the next one.
- Markdown in descriptions renders to HTML, which the templates include
  directly.
- Fonts through `@font-face` from `conf/fonts/`, as today.
- SVG directly: the QR bill from `qrbill` and the logo as SVG instead of a
  PNG with hard-coded dimensions in millimetres.
- The same template renders as HTML in the browser: a live preview on the
  offer page while editing, without generating a PDF.
- PDF metadata (title, author, language), bookmarks from headings, real links
  (e.g. the terms URL), hyphenation from the `lang` attribute.
- PDF/A output (`pdf_variant="pdf/a-3b"`) for archiving. PDF/A-3 also allows embedded files, the basis for e-invoicing
  formats like ZUGFeRD/Factur-X if customers abroad ask for it (not planned).
- Tests can assert on the rendered HTML instead of on PDF bytes.

We already use this approach in other projects (the learning app, the
forum), so it's known territory.

### Costs

- System dependencies: WeasyPrint needs Pango (and HarfBuzz, fontconfig).
  `Containerfile` is based on `ghcr.io/astral-sh/uv:debian`, so an
  `apt-get install libpango-1.0-0 libpangoft2-1.0-0` and fonts config. Local
  development and CI need the same.
- Speed: WeasyPrint is slower than reportlab, typically a few hundred
  milliseconds per document. Fine for single documents; the invoice list
  export (capped at `BATCH_MAX_ITEMS`) and `paid_debtors_zip()` (a yearly
  export) will take longer, measure them.
- The layout has to be redone. All of it, not just the parts which change.

### Structure

```
workbench/documents/              # or workbench/tools/documents.py
    render.py                     # render_offer(), render_invoice(), ...
workbench/templates/documents/
    base.html                     # @page rules, fonts, stationery
    offer.html
    invoice.html
    offers.html                   # cover letter + offers of a project
    dunning_letter.html
    qr_bill.html                  # the QR bill page
    document.css
```

- `render_offer(offer) -> bytes` and friends; the views, the reminder mail
  and the bookkeeping export call these. Rendering functions, no class hierarchy.
- Per-namespace texts stay in `settings.WORKBENCH` for now. Longer texts
  (terms, payment instructions) could become templates per namespace
  (`documents/feinheit/terms.html`) — see open questions.
- Combining several documents (offers of a project, dunning letter with
  invoices) by rendering each to a WeasyPrint `Document` and joining the
  pages, so page numbers restart per document as they do today.
- The QR bill page: `qrbill` writes SVG, embedded inline or as a data URL on
  a named page without margins (`@page qr { margin: 0 }`), positioned at the
  bottom of an A4 page as the standard requires. Check the print size
  carefully, the QR code must be scannable; compare against the current
  output and a real banking app.

### Address window

The address must fit a C5/C6 window envelope (left or right window, Swiss
standard SN 010 130). Today the address frame sits at 20 mm from the left,
5.5–9.5 cm from the top (`address_frame` in `pdf.py`). Keep the position exact when moving to CSS,
`position: absolute` on the first page in millimetres, and test with a
printed page and an envelope.

## 4. Sections and rich text

### Sections

The original request: headings between services, optionally with some text.

Proposal: sections are attributes of services, not separate objects.

```python
class Service(ServiceBase):  # projects.Service
    section_title = models.CharField(_("section title"), max_length=200, blank=True)
    section_description = models.TextField(_("section description"), blank=True)
```

A service with a section title starts a new section; all following services
(by position) belong to it until the next one. The offer PDF renders the
heading and text before the service, and a subtotal per section if there's
more than one section (optional, see open questions).

Why on the service and not a separate `OfferSection` model:

- Services are ordered by `position` already, reordering them keeps the
  heading with the service it introduces. A separate model would need its own
  position in the same sequence.
- Totals, the API, copying offers, creating invoices from offers: all of
  these work on services and keep working unchanged.
- Old offers have empty fields and render exactly as before.

The downside: a section can't exist without a service, and moving the first
service of a section moves the heading along. Acceptable.

The project detail page (services grouped by offer) shows the sections too,
so the structure is visible where offers are edited, not only in the PDF.

Invoices created from offers (`create_services_from_offer`) could copy the
sections to `invoices.Service`. Not needed at first; invoices are usually
shorter and structured by period, not by topic.

### Rich text

Rich text is the main benefit of moving to HTML, so it's part of the first
version, not an afterthought. Lists, emphasis and links are what offers
currently fake with dashes and line breaks, or move into a presentation.

#### Markdown, not an editor

Descriptions are Markdown, stored as text, edited in a textarea and rendered
to HTML when shown. Notes already work this way (`render_markdown()` in
`workbench/tools/markdown.py`, markdown-it-py).

Why not HTML with django-prose-editor (the old `mk/prose-editing` branch
tried it on `Offer.description`):

- Offer texts are mostly written by hand, and people already write
  Markdown without knowing it: dashes for lists, blank lines between
  paragraphs. Markdown makes what they type today render properly.
- Offers created through `wb` and the `workbench-offer` skill: LLMs write
  Markdown without being told; HTML needs a list of allowed tags in the
  skill and sanitising of everything the API receives.
- The text stays readable as it is wherever HTML doesn't fit: service
  choices, the logbook, search, exports, mails, the CLI. No conversion to
  plain text at a dozen call sites.
- Plain text is valid Markdown: no data migration converting formats, no
  breaking change of the APIs.
- No editor JavaScript (which would also have to work in the modal forms),
  readable diffs in the audit log.

The cost: no toolbar. Since the texts are written by hand, that's the main
cost: people write `**bold**` and `- item` without seeing the result. A
hint below the field (as with notes) and a preview in the offer form
(rendered by the server with the same preset) make up for it; the preview
is part of the first version. And existing texts are reinterpreted, see
below.

#### Fields and presets

| Field | Headings | Notes |
|---|---|---|
| `Offer.description` | yes | intro text, may have its own structure |
| `projects.Service.section_description` | yes | see sections above |
| `projects.Service.description` | — | headings would compete with sections |
| `Invoice.description` | yes | |
| `invoices.Service.description` | — | copied from project services |
| `RecurringInvoice.description` | yes | copied to the invoices it creates |

Everywhere: paragraphs, line breaks, bold, italic, bullet and numbered
lists, links (also detected automatically). No images, no tables, no
colours, no font sizes: the document layout decides how things look, the
text only decides structure and emphasis.

Two presets in `workbench/tools/markdown.py`, with and without headings,
each a markdown-it configuration with an explicit list of enabled rules
instead of "CommonMark minus something":

- Raw HTML is escaped (`html: False`), so the output is safe without
  sanitising, in templates as well as in the PDF. markdown-it already
  rejects `javascript:` and similar links.
- Single line breaks stay line breaks (`breaks: True`), as in the plain
  text today.
- Disabled because old texts trigger them by accident and nobody needs
  them in an offer: indented code blocks (four leading spaces), fenced
  code, block quotes (`>`), headings underlined with `---` or `===`
  (setext), horizontal rules, images.
- Headings (`#`) only with the heading preset. They are shifted by one
  level (`#` becomes `<h2>`), the document title is the only `<h1>`. In
  the preset without headings, a line starting with `#` stays text.

Titles (`title`, `section_title`) stay plain text. So do logbook
descriptions, deals etc. Notes use the same Markdown, with the notes'
own configuration.

#### Existing data

No format conversion: every existing text is already Markdown. But some of
them render differently than today. Before the switch, a script lists all
descriptions whose Markdown output differs from today's output beyond
line breaks, grouped by what changes:

- Lines starting with `- ` or `* ` become bullet lists. Mostly what was
  meant, accepted (the layout changes, the content doesn't).
- Lines starting with `1. ` become numbered lists. Accepted if the numbers
  stay the same (markdown-it keeps the start number), checked otherwise.
- `*`, `_` and `**` inside text become emphasis, e.g. footnote stars
  (`Preis*`) or snake_case identifiers. These have to be looked at.
- Lines starting with `#` in fields with headings become headings.
- Lines starting with `+ ` become lists too.

Texts whose meaning would change are escaped in a data migration with
backslashes (`\*`, `\#`), only these characters in only these texts, so
they render exactly as before. Texts which improve (dashes becoming a
list) stay as they are. The script is run against production data and
its output reviewed before writing the migration.

The same applies to the web pages which show descriptions (project, offer
and invoice detail): they render the Markdown too, from the same switch on.

#### Plain text where HTML doesn't fit

The Markdown source is used as it is: `ServiceBase.__str__()` and
`project_service_title()` (service choices, logbook, the planning UI), full
text search, the XLSX and list exports, `title` attributes, mails, and the
GitHub matching which looks for issue URLs in service descriptions (URLs
stay literal in the source). If the markup turns out to be distracting
somewhere (e.g. `**` in service choices), a small `markdown_to_text()`
using the same parser can strip it there; not needed at first.

Copying stays text to text: invoices from offers
(`create_services_from_offer`), from the logbook, from recurring invoices;
copying offers.

#### Markdown in the APIs

The JSON APIs take and return the Markdown source, like today's plain
text. Nothing is stripped or converted. Syntax a field doesn't support
(a heading in a service description) is simply rendered as text.

The `workbench-offer` skill lists what's supported: lists, bold, italic,
links everywhere, headings (`#`, `##`) only in the offer, invoice and
section descriptions.

This is not a breaking change of the API: plain text is valid Markdown.
Older CLI versions keep working.

### API and CLI

- `workbench/offers/api.py`: descriptions as Markdown (above); accept
  `section_title` and `section_description` per service when creating and
  replacing offers; return them in the offer detail. Same for the invoices
  API where it exposes descriptions.
- `wb offers show` prints sections and the descriptions as they are (the
  Markdown source reads fine in a terminal); `wb offers create` takes them
  from the JSON input. Bump the CLI version.
- `workbench-offer` skill: explain when to use sections (a few groups of
  related services, not one section per service), and which Markdown is
  supported (lists, bold, italic, links; headings only in the offer and
  section descriptions).

## 5. Layout

Not specified in detail here, that's a design task. Starting points:

- Logo top left on every page (request from 2025), as SVG.
- Section headings at about H2 size, clearly separated.
- Service rows: title, description, amount aligned right; details (hours ×
  rate, fixed costs) as a secondary line, as today with
  `show_service_details`.
- Optional services visibly different (as today: italic amount, "(optional)"),
  and their total separately.
- Totals block: subtotal, discount, down payments, VAT, total. Keep it
  together on one page.
- Terms and the signature block (agreement) on the last page, kept together.
- Watermark ("In Vorbereitung", "Abgelehnt") as a rotated element on every
  page via a fixed-position element or `@page` background.
- Same base layout for offers, invoices, credits, down payment invoices and
  the dunning letter, so they look like a family.

Before switching, render a sample of real recent offers and invoices with
both renderers side by side and review them.

## 6. Plan

Steps 1 and 2 go live together (the reportlab renderer can't render
Markdown, it would print the markup); they can be developed and reviewed
separately.

1. **WeasyPrint renderer** for offers, invoices (QR bill, credits, down
   payments), the dunning letter and the project offers PDF. System
   dependencies in the container, templates, CSS, fonts, logo. Developed
   behind `?renderer=weasyprint` to compare against reportlab, with plain
   text descriptions rendered through `linebreaks` in the meantime.
2. **Markdown**: the two presets, rendering in the document templates and
   on the web pages, the hint and a preview in the forms, the skill update. The
   script listing old texts which render differently, its review, and the
   data migration escaping the texts whose meaning would change.
   From then on WeasyPrint is the only renderer for offers and invoices; remove
   `process_offer()`, `process_invoice()` and friends from `pdf.py`. Keep
   `PDFDocument` for the internal reports (or move those too, later).
3. **Sections** on services: model, form, project detail page, offer
   template, API, CLI, skill.
4. Maybe: a preview of the whole document on the offer page while editing,
   PDF/A, storing sent documents (section 2).

## 7. Open questions

- Subtotals per section: always, never, or a checkbox on the offer?
- Unsupported Markdown (e.g. a heading in a service description): render it
  as text (the default), or warn in the form and the API? A warning teaches
  LLMs the rule through the response; rejecting would be too strict for
  old texts.
- With headings allowed in the offer description, are sections still needed
  as fields, or could the offer description and service descriptions carry
  all the structure? Sections are the only way to put text *between*
  services, so probably yes.
- Terms and payment texts: keep them as settings, or move them into
  per-namespace templates now that documents are HTML?
