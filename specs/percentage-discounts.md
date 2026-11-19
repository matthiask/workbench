# Spec: Percentages for discounts and down payments

## Goal

Basecamp to-do "Manuelles Prozentrechnen vermeiden (Anzahlungsrechnungen,
Rabatte)?" (November 2026): people compute discounts and down payments in
a spreadsheet next to Workbench and enter the result as an amount. That's
tedious and error-prone: was the base right, were third party costs left
out, was the discount of a partially invoiced offer split correctly?

Wanted:

- Down payments as x% of the accepted offers, optionally without third
  party costs.
- Discounts on offers as x% of our own services (without third party
  costs).
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
- **Offer discounts are given proportionally** on the invoices which
  invoice the offered services, so that the customer has got the whole
  discount once the offer has been invoiced. Where that isn't the case,
  the final invoice makes it obvious.
- **No defaults per project or customer.**
- **Rounding**: every amount the helpers fill in (discounts, shares,
  down payments) is rounded to 5 cents, as is customary here. Totals
  incl. tax are rounded to 5 cents as today.

## 1. Today

### Discounts

- `ModelWithTotal.discount` (`workbench/tools/models.py`) is an amount on
  offers, invoices and recurring invoices. `total_excl_tax = subtotal −
  discount − down_payment_total`.
- Offers: `subtotal` is the sum of `service_cost` of the non-optional
  services (`Offer._calculate_total()`). The discount is entered in the
  offer form below the services; `main.js` recalculates the totals live.
- Services invoices created from an offer copy the offer's discount, but
  only if none of the offer's services has been invoiced yet (not
  cancelled) — "the offer's discount once, not again when invoicing the
  surplus" (`CreateProjectInvoiceForm`). Invoicing a part of the offer
  gets all of the discount; invoices without an offer get none.
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

## 2. Own services

The base of percentage discounts, a helper on `ServiceBase` (e.g.
`own_cost`): `service_cost − (third_party_costs or 0)`. Effort, costs
without third party costs (e.g. fees for open data) and markups on third
party costs count; what we pay others doesn't. For an offer: Σ over its
non-optional services.

## 3. Down payments: percentage helper

- Next to the amount of down payment and fixed amount invoices: a
  percentage input and a choice of base:
  - **Accepted offers**: Σ `total_excl_tax` of the accepted offers (as
    today).
  - **Without third party costs**: the same minus the third party costs
    of their non-optional services (`accepted_offers_by_project()` has
    them already).
- Typing a percentage fills in the amount, rounded to 5 cents. The 50%
  and 100% links stay as shortcuts (of the first base).
- No automatic text in the description.
- API and CLI: unchanged, they take amounts.

No selection of services as a base (Andreas: "Auswahlbox") for now: the
two bases first, and wait for a case.

## 4. Offers: percentage helper for the discount

- Offer form, totals below the services: next to the discount amount a
  percentage input "% of own services". Typing a percentage fills in the
  amount (live in `main.js`, which then needs the third party costs of
  each service row, they're in the form already).
- When the form is shown, the percentage shows what the stored amount
  amounts to (e.g. "10.0%"), so that it's visible how a discount was
  meant. Changing services doesn't change the amount; the percentage
  shown follows, which makes it obvious when the discount should be
  adjusted.
- Offers which can't be changed anymore can't change their discount
  (as today).
- PDF, API and CLI unchanged. The `workbench-offer` skill computes the
  amount from the own services when asked for a percentage (the services
  and their third party costs are in `wb offers show`).

## 5. Invoices: the discounts of the offers

### Prefilled: the proportional share

Creating a services invoice prefills the discount with the proportional
share of the discounts of the accepted or offered (not declined) offers
whose services are invoiced. Per offer with a discount:

```
own(offer)      = Σ own cost of its non-optional services
invoiced(offer) = Σ own cost of the lines of earlier invoices (not
                  cancelled) on services of this offer
this(offer)     = Σ own cost of this invoice's lines on services of this
                  offer
given(x)        = offer.discount × min(1, x / own(offer)), rounded to 5 cents
share(offer)    = given(invoiced + this) − given(invoiced)
```

The invoice's discount is Σ `share`. Since `given()` is rounded before
subtracting, the shares add up to exactly the offer's discount (if the
offer's discount itself is a multiple of 5 cents). This replaces today's rule "the
offer's discount once, on the first invoice":

- Partial invoices get their share, the rest follows with the rest of
  the offer.
- Invoicing more than offered (surplus) gets nothing beyond the offer's
  discount: once the offer's own services are invoiced, the whole
  discount has been given.
- Services without offer get nothing.
- It doesn't matter in which order the services are invoiced, nor
  whether the lines were invoiced "as offered" or "as logged".

The amount stays editable. Recomputed (with JS or on a reload) when the
selection of lines changes; once edited by hand, it's left alone.

### Help text: what the offers granted, and helpers

Below the discount, if any offer of the project has a discount:

- Per offer: "Offer 2027-0012-01 Konzept: discount 2,000.00 (10.0% of own
  services), 1,000.00 given so far."
- Links which fill in the amount:
  - "Share of the offers' discounts: x" (the prefilled value).
  - "Remaining discounts of the offers: y" (Σ `offer.discount −
    given(invoiced)`), e.g. for a final invoice which invoiced less than
    offered.
  - "x% of the own services of this invoice", one link per distinct
    percentage of the offers (e.g. 10%, 5%), for an analogous discount
    on the surplus or on services without offer.
- The same percentage input as on offers ("% of own services").

### Final invoices

Services and fixed amount invoices alike: when the invoice closes the project ("This is the final invoice"), or the
project is closed, and accepted offers' discounts haven't been given in
full (Σ remaining > 0 after this invoice): a warning "The offers granted
discounts of x, the invoices so far gave y." with the link to apply the
remaining discount. Only a warning: if less was delivered than offered,
the smaller share may be right.

"Given" compares at the project level: Σ `discount` of the project's
invoices (not cancelled) against Σ `discount` of its accepted offers.
The overall discount is what matters; invoice discounts aren't linked to
offers, and manual discounts (e.g. on the surplus) count too.

### Other invoice types

- Fixed amount and down payment invoices: no prefilled discount. The
  down payment base of section 3 is after discounts already. Final fixed
  amount invoices get the same final invoice warning: the invoicing mode
  doesn't change that a discount has been offered.
- Credits and recurring invoices: unchanged.

### API

The API creates services invoices through the same form, so it gets the
prefilled share too (today: the whole discount once). `discount` in the
request still overrides it. Test in `workbench/test_cli.py`.

## 6. Example

Project "Kampagne 2027":

| Offer | Own services | Third party costs | Discount | Total excl. tax |
|---|---|---|---|---|
| A Konzept | 20,000 | 2,000 | 2,000 (entered as 10%) | 20,000 |
| B Umsetzung | 40,000 | – | 2,000 (entered as 5%) | 38,000 |

1. Down payment 30%: on the accepted offers 58,000 → 17,400; without
   third party costs 56,000 → 16,800.
2. Invoice 1, half of A's services (own 10,000): discount prefilled with
   1,000.
3. Invoice 2, the rest of A (own 10,000) and all of B (own 40,000) plus
   3,000 surplus on B and a new service without offer (1,500): prefilled
   1,000 (A) + 2,000 (B, capped) = 3,000. The help text offers "5% of the
   own services of this invoice" if the project manager wants to give
   the 5% on the surplus too.
4. Had invoice 2 invoiced only 36,000 of B's own services (less work than
   offered), it would prefill 1,800 for B, and as the final invoice show
   "The offers granted discounts of 4,000, the invoices so far gave
   3,800" with a link to apply the remaining 200.

## 7. Reports and key figures

Nothing changes in the computations: they use the stored `discount` and
`total_excl_tax`. Which invoices carry how much discount changes (split
instead of all on the first one), which is closer to reality for partially
invoiced offers. `docs/metrics.md` stays as it is unless it describes the
"once" rule; `docs/offers.md` and `docs/invoices.md` (both languages)
describe the helpers and the proportional discount.

## 8. Implementation steps

One commit each, tests first:

1. `own_cost` helper and the down payment percentage helper (section 3).
2. Offer discount percentage helper (section 4).
3. Proportional discount on services invoices, replacing the "once" rule,
   with the help text and its links (section 5).
4. Final invoice warning (section 5).
