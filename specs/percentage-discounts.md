# Spec: Percentages for discounts and down payments

## Goal

Basecamp to-do "Manuelles Prozentrechnen vermeiden (Anzahlungsrechnungen,
Rabatte)?" (November 2026): people compute discounts and down payments in
a spreadsheet next to Workbench and enter the result as an amount. That's
tedious and error-prone: was the base right, were third party costs left
 out, has the customer got the whole discount in the end?

Wanted:

- Down payments as x% of the accepted offers, optionally without third
  party costs.
- Discounts on offers as x% of the services excl. third party costs.
- Invoices give the customer the discounts of their offers, without
  computing them by hand.

## Decisions

- **Input helpers, nothing new is stored.** Discounts and down payments
  stay amounts. Percentages are a way to enter them, shown with the base
  they're computed from. A stored percentage would raise questions we
  don't want to answer in general (does it apply to the surplus, to
  services added later, to services without offer?). Past discounts
  don't have to be carried forward; the project manager sees them and
  can apply an analogous discount when it makes sense.
- **The total matters, not each invoice.** The customer should have got
  the offers' discounts once the project has been invoiced; which invoice
  carries how much doesn't matter. No proportional shares per invoice.
- **Discounts are prefilled only when invoicing an offer.** Invoices
  created on the project start without discount.
- **Context instead of warnings.** No new warnings (`WarningsForm`): the
  forms show the facts (what the offers granted, what has been invoiced
  and discounted so far) and input helpers next to the fields.
- **No defaults per project or customer.**
- **Rounding**: every amount the helpers fill in (discounts, down
  payments) is rounded to 5 cents, as is customary here. Totals incl. tax
  are rounded to 5 cents as today.

## 1. Today

### Discounts

- `ModelWithTotal.discount` (`workbench/tools/models.py`) is an amount on
  offers, invoices and recurring invoices. `total_excl_tax = subtotal −
  discount − down_payment_total`.
- Offers: `subtotal` is the sum of `service_cost` of the non-optional
  services (`Offer._calculate_total()`). The discount is entered in the
  offer form below the services; `main.js` recalculates the totals live.
- Services invoices created from an offer (the offer's menu, `offer` in
  the API) copy the offer's discount, but only if none of the offer's
  services has been invoiced yet (not cancelled) — "the offer's discount
  once, not again when invoicing the surplus" (`CreateProjectInvoiceForm`).
  Invoices created on the project get none.
- A services invoice may mix services of several offers and services
  without offer. It has one discount.
- PDFs show one line "discount −x" in the totals (`workbench/tools/pdf.py`).
- Reports use `total_excl_tax` (after the discount) and Σ `discount`
  (`accepted_offers_by_project()`, budget statistics). Gross margin is
  after discounts, third party costs aren't discounted
  (`Offer.gross_margin`, `Invoice.gross_margin`).

### Down payments

- Down payment and fixed amount invoices: the amount's help text shows
  the total excl. tax of the accepted offers (`accepted_offers_by_project()`,
  after discounts, without optional services, budget retainers included)
  and links "50%" and "100%" which fill in the amount.
- The final invoice deducts the down payments' `total_excl_tax`.

## 2. Service cost excl. third party costs

The base of percentage discounts, a helper on `ServiceBase`:
`service_cost_excl_third_party_costs = service_cost − (third_party_costs
or 0)`. A long name rather than a new, unexplained term: Workbench
already says "service cost" and "third party costs". Effort, costs
without third party costs (e.g. fees for open data) and markups on third
party costs count; what we pay others doesn't. The same name on `Offer`:
Σ over its non-optional services. Labelled "services excl. third party costs"
("Leistungen ohne Fremdkosten").

## 3. Down payments and fixed amount invoices

Down payments and fixed amount invoices show no discount: their base is
the accepted offers after discounts, so a 50% down payment is half of
what the customer pays for the offers, and the final invoice deducts it
as today.

- Next to the amount: a percentage input and a choice of base:
  - **Accepted offers**: Σ `total_excl_tax` of the accepted offers (as
    today).
  - **Without third party costs**: the same minus the third party costs
    of their non-optional services (`accepted_offers_by_project()` has
    them already).
- Typing a percentage fills in the amount, rounded to 5 cents. The 50%
  and 100% links stay as shortcuts (of the first base).
- The facts, so that the total can be checked, if the project has
  accepted offers:
  - the accepted offers' total,
  - invoiced so far: Σ (`subtotal − discount`) of the project's fixed
    amount and services invoices (not cancelled), i.e. the work invoiced,
    without deducting down payments,
  - the down payments: Σ `total_excl_tax` of the down payment invoices
    (not cancelled), and how much of it hasn't been applied yet,
  - the rest: accepted offers − invoiced so far.
- Fixed amount invoices get a link filling in the rest. The final
  invoice deducts the down payments selected under "Apply down payment
  invoices" from it, as today. Counting the down payments in "invoiced
  so far" would deduct them twice. Down payment invoices get no such
  link: a down payment of the whole rest isn't wanted.
- Shown when creating and when editing invoices in preparation (today
  the 50% and 100% links only appear when creating).
- No automatic text in the description.
- API and CLI: unchanged, they take amounts.

No selection of services as a base (Andreas: "Auswahlbox") for now: the
two bases first, and wait for a case.

## 4. Offers: percentage helper for the discount

- Offer form, totals below the services: next to the discount amount a
  percentage input "% of the services excl. third party costs". Typing a
  percentage fills in the amount (live in `main.js`, which then needs the
  third party costs of each service row, they're in the form already).
- When the form is shown, the percentage shows what the stored amount
  amounts to (e.g. "10.0%"), so that it's visible how a discount was
  meant. Changing services doesn't change the amount; the percentage
  shown follows, which makes it obvious when the discount should be
  adjusted.
- Offers which can't be changed anymore can't change their discount
  (as today).
- PDF, API and CLI unchanged. The `workbench-offer` skill computes the
  amount from the services excl. third party costs when asked for a
  percentage (the services and their third party costs are in `wb offers
  show`).

## 5. Services invoices

### Invoicing an offer: the offer's discount

Creating a services invoice from an offer prefills the offer's whole
discount unless an earlier invoice (not cancelled) with lines on this
offer's services carries a discount. Today's rule looks at whether any of
the offer's services has been invoiced; looking at the discounts instead
means that a first partial invoice without discount (e.g. a deliberate
one) doesn't lose the discount for the next one, and invoicing the
surplus still gets none.

Open: an earlier invoice mixing services of several offers counts for
each of them, although its discount may have been meant for one only.
Rare (invoices from an offer contain that offer's services); the facts
below show it. Likewise, a partial invoice which gave only a part of the
discount by hand means that the next one gets none prefilled; the
remaining discount and its link below catch that.

Invoicing a part of the offer gets the whole discount, as today. The
amount stays editable; the facts below show what's left.

### Invoices on the project: no discount, the facts

Invoices created on the project start without discount. Below the
discount, on services invoices of a project with discounted offers, when
creating them and when editing them in preparation:

- Per offer (accepted or offered, not declined) with a discount:
  "Offer 2027-0012-01 Konzept: discount 2,000.00 (10.0% of the services
  excl. third party costs)." Offers which haven't been accepted yet are
  marked as such.
- The total: "The accepted offers granted discounts of x, the invoices
  so far gave y." Compares at the project level, Σ `discount` of the
  project's invoices (not cancelled) against Σ `discount` of its
  accepted offers; manual discounts (e.g. on the surplus) count too.
  Credits don't count: there have been three in all (the last in 2024),
  and what was paid is a fact.
- Links which fill in the amount:
  - "Remaining discount: x − y" (if positive), e.g. for a final invoice.
  - "x% of the services excl. third party costs of this invoice", one
    link per distinct percentage of the offers (e.g. 10%, 5%), for an
    analogous discount on the surplus or on services without offer.
- The same percentage input as on offers.

The percentage and the link of this invoice follow the selected lines
live (`updateInvoiceTotals()` in `main.js`). The rows don't know their
third party costs today: each source (as offered, as logged) gets a data
attribute with its third party costs, like its hours and costs
(`create_services_from_offer()`: the service's third party costs, or the
logged ones). The rows show them ("thereof third party costs x"), and
the totals show the services excl. third party costs, which helps
interpreting the percentages. A cost edited below its third party costs
counts at most the cost as third party costs.

Credits and recurring invoices: unchanged.

### API

The API creates services invoices through the same form, so it follows
the new rule when `offer` is given; `discount` in the request still
overrides it. Test in `workbench/test_cli.py`.

## 6. Example

Project "Kampagne 2027":

| Offer | Services excl. third party costs | Third party costs | Discount | Total excl. tax |
|---|---|---|---|---|
| A Konzept | 20,000 | 2,000 | 2,000 (entered as 10%) | 20,000 |
| B Umsetzung | 40,000 | – | 2,000 (entered as 5%) | 38,000 |

1. Down payment 30%: on the accepted offers 58,000 → 17,400; without
   third party costs 56,000 → 16,800. No discount on the down payment.
2. Invoice 1 from offer A, half of its services: discount prefilled with
   2,000 (the whole discount of A).
3. Invoice 2 from offer A, the rest: no discount, invoice 1 carries one.
   The help text says "The offers granted discounts of 4,000, the
   invoices so far gave 2,000."
4. Invoice 3 on the project, all of B plus 3,000 surplus and a new
   service without offer: no discount prefilled. The help text offers
   "Remaining discount: 2,000" and "5% of the services excl. third party
   costs of this invoice" if the project manager wants to give the 5% on
   the surplus too.
5. Had the project been invoiced with a final fixed amount invoice
   after the down payment instead, its help text would show the accepted
   offers' total 58,000 (after discounts), invoiced so far 0, the down
   payment 17,400 (not applied yet) and the rest 58,000. The link fills
   in 58,000, applying the down payment deducts 17,400: total excl. tax
   40,600.

## 7. Reports and key figures

Nothing changes in the computations: they use the stored `discount` and
`total_excl_tax`. `docs/metrics.md` stays as it is unless it describes the
"once" rule; `docs/offers.md` and `docs/invoices.md` (both languages)
describe the helpers and when invoices get the offers' discount
(`docs/invoices.md`: "Choosing an offer takes its title, description,
services and discount" gets the new rule).

## 8. Implementation steps

One commit each, tests first:

1. `service_cost_excl_third_party_costs` (services and offers) and the
   down payment percentage helper with the facts and the rest link,
   also when editing (sections 2 and 3).
2. Offer discount percentage helper (section 4).
3. Invoicing an offer: the discount unless an earlier invoice of its
   services carries one (section 5).
4. The facts and links in services invoice forms, the third party costs
   of the rows (section 5).

## 9. Status and questions for review

Steps 1–4 are implemented (and the `workbench-offer` skill, CLI 0.52.1).
Open questions, decided provisionally:

1. **The API didn't give offer discounts at all**: `InvoiceIn.discount`
   defaulted to 0, so `wb invoices create --offer` never got the offer's
   discount (section 1 assumed it did). It now defaults to the form's value
   (the offer's discount until an invoice of its services carries one).
   That changes what `wb` and the skills create, e.g. the
   `lmvz-offerten` skill creating invoices per offer. Right?
2. **Third party costs aren't fields of the offer form** (section 4
   assumed they were). The rows carry the stored third party costs as a
   data attribute; new services and changed costs use those, so the base
   is only exact after saving.
3. **Third party costs are capped at the cost**, in Python
   (`service_cost_excl_third_party_costs`) and in JavaScript, since they're
   a part of the cost.
4. **Offers in preparation** aren't listed in the discount help of services
   invoices, only offered and accepted ones (they're not a promise to the
   customer yet).
5. **"Invoiced so far" on fixed amount invoices** includes services
   invoices of work beyond the offers (surplus, services without offer),
   so the rest may be too low on such projects. It's a fact next to the
   field, not a rule; leave it?
6. **German wording**: "Verrechne 50%, 100% oder [ ]% von akzeptierte
   Offerten" (the select's labels are lowercase nouns) and "Verwende … oder
   [ ]% von den Leistungen ohne Fremdkosten dieser Rechnung". Better
   phrasing welcome.
7. **Percentages are shown with one decimal** and recomputed from the
   rounded amount once the input loses focus, e.g. 33.33% shows as 33.3%.
8. The JavaScript formats amounts with `'` (de-CH), the server with `’`;
   pre-existing in the invoice form, visible now that both are next to each
   other.
