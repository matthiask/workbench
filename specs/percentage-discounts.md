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
party costs count; what we pay others doesn't. For an offer: Σ over its
non-optional services. Labelled "services excl. third party costs"
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
- The facts, so that the total can be checked: the accepted offers'
  total, invoiced so far (Σ `total_excl_tax` of the project's invoices,
  not cancelled, down payments included) and the rest, with a link
  filling in the rest.
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
below show it.

Invoicing a part of the offer gets the whole discount, as today. The
amount stays editable; the facts below show what's left.

### Invoices on the project: no discount, the facts

Invoices created on the project start without discount. Below the
discount, on all services invoices of a project with discounted offers:

- Per offer (accepted or offered, not declined) with a discount:
  "Offer 2027-0012-01 Konzept: discount 2,000.00 (10.0% of the services
  excl. third party costs)."
- The total: "The offers granted discounts of x, the invoices so far gave
  y." Compares at the project level, Σ `discount` of the project's
  invoices (not cancelled) against Σ `discount` of its accepted offers;
  manual discounts (e.g. on the surplus) count too.
- Links which fill in the amount:
  - "Remaining discount: x − y" (if positive), e.g. for a final invoice.
  - "x% of the services excl. third party costs of this invoice", one
    link per distinct percentage of the offers (e.g. 10%, 5%), for an
    analogous discount on the surplus or on services without offer.
- The same percentage input as on offers.

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
5. Had the project been invoiced with a fixed amount invoice instead,
   its help text would show the accepted offers' total (58,000, after
   discounts), invoiced so far and the rest.

## 7. Reports and key figures

Nothing changes in the computations: they use the stored `discount` and
`total_excl_tax`. `docs/metrics.md` stays as it is unless it describes the
"once" rule; `docs/offers.md` and `docs/invoices.md` (both languages)
describe the helpers and when invoices get the offers' discount.

## 8. Implementation steps

One commit each, tests first:

1. `service_cost_excl_third_party_costs` and the down payment percentage
   helper with the invoiced so far facts (sections 2 and 3).
2. Offer discount percentage helper (section 4).
3. Invoicing an offer: the discount unless an earlier invoice of its
   services carries one (section 5).
4. The facts and links in services invoice forms (section 5).
