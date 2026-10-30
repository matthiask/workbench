# Spec: Reworking offer and invoice documents

## Goal

Offers should be able to explain themselves. Today an offer is a flat list of
services below an optional intro text; whenever the scope needs some structure
we send a presentation along to explain it. People asked for section headings
with some body text between the services (Basecamp to-do "Zwischentitel und
Zwischen-Fliesstext für Workbench-Offerten", March 2024), and later for the
logo on offers and invoices.

Instead of bolting this onto the current reportlab code, this spec proposes
to render offers and invoices from HTML templates with WeasyPrint, to give
offers a structure (sections), and to freeze documents once they have been
sent so that changing the layout doesn't change documents customers already
have.

The layout of new documents will change a lot. That's accepted. Documents
which have been sent must not change.

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
`PDF_INVOICE_PAYMENT` (bank account!), or to a related object (the owner's
name in "Our reference", a project title used in the filename) already
changes documents which were sent years ago. The bookkeeping export then
contains invoices which aren't what the customer received. That's a problem
independent of this rework, the rework just makes it impossible to ignore.

### Other users of `PDFDocument`

Not offers or invoices, internal only, out of scope here and can stay on
reportlab for now:

- annual working time and user statistics (`workbench/awt/pdf.py`)
- expense reports (`workbench/expenses/views.py`)

## 2. Freezing sent documents

Do this first, before touching the layout. It's useful on its own.

### Model

A small model in a new app or in `workbench/tools`, shared by offers and
invoices:

```python
class Document(models.Model):
    content_type / object_id  # or two nullable FKs, see open questions
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(User, ...)
    file = models.FileField(upload_to="documents/%Y/%m/")
    sha256 = models.CharField(max_length=64)
    renderer = models.CharField(max_length=20)  # "reportlab", "weasyprint-1"
```

Several documents per offer or invoice are allowed: an offer which goes back
into preparation and is sent again gets a second document, the first one
stays as a record of what was sent.

### When to freeze

- Offers: on the first transition from *in preparation* (or *service group*)
  to *offered*. Accepting or declining doesn't create a new document.
- Invoices: on the transition from *in preparation* to *sent*.
- When a document goes back to *in preparation*, the frozen PDF stays but
  isn't served anymore; the next transition freezes a new one.

### Serving

`OfferPDFView` and `InvoicePDFView` serve the latest frozen document if the
offer or invoice isn't in preparation, and render live otherwise. A
`?live=1` parameter (staff, controlling) renders live anyway, e.g. to compare
the layouts. Same for the invoice list export, the reminder mail and
`paid_debtors_zip()`.

The dunning letter itself is generated live (it's dated today), the attached
invoices are frozen documents. With reportlab we can't append existing PDFs
to the story; with frozen files we concatenate PDFs instead (`pypdf`, or
WeasyPrint's own `Document` objects, see below).

### Backfill

A management command renders and freezes every offer and invoice which isn't
in preparation, with the current reportlab renderer, marked
`renderer="reportlab"`. Run it once right before deploying anything which
changes the layout. This is the moment the old documents get fixed; it's not
exactly what customers received (see above, the settings and related objects
may have changed since), but it's the closest we'll get, and it stops drifting
from then on.

Estimate the size: a few thousand invoices and offers at 30–100 KB each,
a few hundred MB at most. The default storage is the filesystem; the volume
needs to be backed up together with the database. Check how media files are
handled in the deployment (there are none yet).

### Payment instructions and QR bill

Freezing also fixes the bank account: a frozen invoice keeps the IBAN and the
QR bill it was sent with even when `QRBILL` changes.

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
- Rich text in descriptions is just HTML.
- Fonts through `@font-face` from `conf/fonts/`, as today.
- SVG directly: the QR bill from `qrbill` and the logo as SVG instead of a
  PNG with hard-coded dimensions in millimetres.
- The same template renders as HTML in the browser: a live preview on the
  offer page while editing, without generating a PDF.
- PDF metadata (title, author, language), bookmarks from headings, real links
  (e.g. the terms URL), hyphenation from the `lang` attribute.
- PDF/A output (`pdf_variant="pdf/a-3b"`) for archiving, which suits frozen
  documents. PDF/A-3 also allows embedded files, the basis for e-invoicing
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
  export and `paid_debtors_zip()` mostly serve frozen documents anyway after
  section 2.
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

- `render_offer(offer) -> bytes` and friends; the views and `Document`
  freezing call these. Rendering functions, no class hierarchy.
- Per-namespace texts stay in `settings.WORKBENCH` for now. Longer texts
  (terms, payment instructions) could become templates per namespace
  (`documents/feinheit/terms.html`) — see open questions.
- Combining several documents (offers of a project, dunning letter with
  invoices) by rendering each to a WeasyPrint `Document` and joining the
  pages, so page numbers restart per document as they do today. Frozen PDFs
  are concatenated with `pypdf`.
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

## 4. Structured offers

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

Descriptions of offers and services are plain text today. With HTML
rendering they could be rich text (django-prose-editor, see the old
`mk/prose-editing` branch which used `RestrictedProseField` with headings,
bold, italics, sub/sup and hard breaks).

Recommendation: start with sections and keep descriptions plain text, but
render them better (paragraphs from blank lines, `linebreaks` filter). Add rich
text later and only for a few fields (offer description, section description)
if sections aren't enough. Reasons:

- Descriptions are also used outside the PDF: the project detail page, search
  (`_fts`), XLSX exports, service titles in the logbook, invoices created from
  offers, the JSON APIs and `wb`. All of these would need an HTML and a text
  version.
- The offers API is mostly fed by LLMs through `wb` and the `workbench-offer`
  skill. Plain text (or Markdown converted on the server) is easier for them
  than sanitised HTML.
- A heading inside a service description competes with the section headings
  and makes the structure arbitrary again.

If we do add rich text: a separate field or a format marker per object, so
that old plain-text descriptions keep rendering as plain text. Never
reinterpret existing text as Markdown or HTML (a line starting with `#` or a
`*` in an old description must not change meaning).

### API and CLI

- `workbench/offers/api.py`: accept `section_title` and
  `section_description` per service when creating and replacing offers; return
  them in the offer detail.
- `wb offers show` prints sections; `wb offers create` takes them from the
  JSON input. Bump the CLI version.
- `workbench-offer` skill: explain when to use sections (a few groups of
  related services, not one section per service).

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

Each step can be deployed on its own.

1. **Freeze documents** with the current renderer: `Document` model,
   freezing on status transitions, serving frozen documents, backfill
   command, concatenating frozen PDFs for the dunning letter and the
   bookkeeping export. No visible change.
2. **WeasyPrint renderer for offers**, behind a setting or feature flag so it
   can be compared (`?renderer=weasyprint`). System dependencies in the
   container. Templates, CSS, fonts, logo.
3. **Sections** on services: model, form, project detail page, offer
   template, API, CLI, skill. Only rendered by the new renderer.
4. **WeasyPrint for invoices** including the QR bill, credits, down
   payments; then the dunning letter and the project offers PDF.
5. Switch the default, remove `process_offer()`, `process_invoice()` and
   friends from `pdf.py`. Keep `PDFDocument` for the internal reports (or
   move those too, later).
6. Maybe: rich text for offer and section descriptions, HTML preview on the
   offer page, PDF/A.

Old offers and invoices are unaffected from step 1 on: they're frozen with
the layout they were sent with.

## 7. Open questions

- Generic relation or two nullable FKs (`offer`, `invoice`) on `Document`?
  Two FKs are simpler to query and to protect (`on_delete=PROTECT`).
- Should a frozen offer still be regenerated when its *status* changes the
  watermark? Today a declined offer shows "Abgelehnt"; a frozen one would
  show the clean version that was sent. Probably that's right, the watermark
  is for internal use.
- Subtotals per section: always, never, or a checkbox on the offer?
- Should `paid_debtors_zip()` still be able to regenerate (`qr=False` today
  produces invoices without the QR page)? With frozen documents the QR page
  would be included; drop the parameter or strip the last page.
- Terms and payment texts: keep them as settings, or move them into
  per-namespace templates now that documents are HTML?
- Where do media files live in production, and how are they backed up?
- Does anybody rely on regenerated PDFs picking up corrections (e.g. a fixed
  typo in the postal address of a sent invoice)? With freezing, a correction
  means a credit and a new invoice, or an explicit "re-freeze" action for
  admins.
