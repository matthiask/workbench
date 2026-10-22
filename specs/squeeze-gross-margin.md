# Spec: How squeeze works, and two fixes

## Goal

Document how squeeze estimates gross margin per project and attributes it to
people, then fix two problems found in October 2026:

1. **Third party costs are subtracted twice** when costs are logged on a
   project but invoiced through invoices which aren't linked to those logged
   costs (fixed amount and down payment invoices, or services invoices created
   from the offer before the costs were logged). Example: a campaign
   with a pass-through media budget ("project A" below).
2. **Work logged on services with an hourly rate of 0.-/h gets no share of the
   gross margin**, e.g. programming on campaign websites sold at a package
   price. Example: the developers on a campaign with a campaign website
   ("project B" below).

The fixes have to work for projects whose invoices are already frozen.

---

## 1. How squeeze works today

All code is in `workbench/reporting/squeeze.py`. `squeeze_data(date_range)`
builds the report (web view, XLSX, `key_data_api`). `project_gross_margin(project)`
computes the same numbers for one project (profitability modal on the project
page). Both have to stay in sync.

### 1.1 Gross margin per project (all time)

For every project with hours logged in the period:

| Value | Computation |
|---|---|
| `invoiced` | Σ `total_excl_tax` − Σ `third_party_costs` of invoices with status sent or paid, **minus** Σ `LoggedCost.third_party_costs` where `invoice_service IS NULL` |
| `offered` (open projects only) | Σ `total_excl_tax` of accepted offers − Σ `Service.third_party_costs` of those offers |
| `projected` (open projects only) | Σ `ProjectedInvoice.gross_margin` (entered by hand, already net of third party costs) |
| `gross_margin` | `max(offered, projected, invoiced) + BudgetTransfer adjustment`, floored at 0 |

The max() means: whichever source is the most complete wins. For closed
projects only `invoiced` is left, so it is the ground truth there.

`Invoice.third_party_costs` is "only used for statistical purposes":

- *Services* invoices recompute it from their services in
  `_calculate_total()`. When created from the logbook, a service's third party
  costs are the sum of the logged costs (which get linked through
  `invoice_service` and archived). When created from the offer, they are the
  **offered** third party costs, and only logged costs which already exist at
  that point are linked.
- *Fixed amount* and *down payment* invoices have no services. The third party
  costs are entered by hand and logged costs can never be linked to them.

### 1.2 Relevant hours and rate

```
hours = max(hours_offered, hours_logged_budgeted) + hours_logged_unbudgeted
rate  = gross_margin / hours
```

`hours_offered` are the budgeted service hours (open projects only), unbudgeted
hours (optional / declined services) are added on top so that we rather
underestimate (see AGENTS.md).

### 1.3 Attribution to people

The project's margin is sliced by time: the period gets
`hours_in_period / hours × gross_margin`. This slice is then split between the
people who logged hours in the period, weighted by `hours × effort_rate` of the
service they logged on:

```python
F("hours") * Coalesce(F("service__effort_rate"), Value(EXPECTED_AVERAGE_HOURLY_RATE))
```

Services without a rate (`NULL`) fall back to 150.-/h and are reported as
"hours at default rate". Services with a rate of **0.00 are not NULL**, so they
get a weight of 0.

`EXPECTED_AVERAGE_HOURLY_RATE` (150.-/h) doesn't describe what the constant is
anymore. Since specialist fields have their own expected hourly rates, it is
the base rate: the fallback weight for hours without a rate, the expected rate
for people without a specialist field, and the threshold below which rates
are shown in red. Rename it to `BASE_HOURLY_RATE`.

### 1.4 Per person, specialist field, organization

Per person: Σ attributed margin, compared against
`expected_hourly_rate × 8h × (working days − absences) × profitable % × employment %`.
Specialist fields and organizations are sums of the per-person values.

---

## 2. Problem 1: Third party costs subtracted twice

### What happens in project A

| | Amount |
|---|---:|
| Invoiced excl. tax (several invoices) | ~157'000 |
| Third party costs on invoices | ~−97'000 |
| Logged third party costs not linked to an invoice service | ~−94'000 |
| **`invoiced`** | **~−35'000** |

The project is closed, so `gross_margin = max(0, −35'000) = 0` and the rate
is 0.-/h on ~300h. Everyone on the project gets nothing for it.

The unlinked logged costs are:

- ~90'000 media budget (ads, paid by credit card). Invoiced through
  *fixed amount* invoices (the media budget entered as third party costs).
  These can't ever be linked.
- A few thousand for translations and licenses. Invoiced through a services
  invoice which was created from the offer (third party costs = offered
  amounts). The costs were logged after the invoice was created and so stayed
  unlinked.

Correct is roughly 157'000 − 97'000 = **60'000**, i.e. ~190.-/h.

### How common is this

Projects with unlinked logged third party costs since 2025-10 where the
invoices carry more third party costs than the linked logged costs (i.e. the
costs are probably already accounted for):

| Project | Unlinked logged | On invoices | Possible double count |
|---|---:|---:|---:|
| Project A (media budget) | ~95'000 | ~95'000 | ~95'000 |
| Project C | ~20'000 | ~20'000 | ~20'000 |
| Project D | ~20'000 | ~20'000 | ~20'000 |
| Project E | ~10'000 | ~10'000 | ~10'000 |
| Project F–H | < 5'000 each | | < 5'000 each |
| 4 more | | | small amounts |

~10 projects, up to ~150'000 counted twice. Almost all of them use fixed amount
invoices to pass through media budgets, licenses or travel costs.

### Proposed fix

#### a) Don't add up, take the larger value (automatic)

Instead of *invoiced third party costs + unlinked logged third party costs*,
subtract

```
third_party_costs = max(
    Σ Invoice.third_party_costs,
    Σ LoggedCost.third_party_costs (linked and unlinked),
)
```

Reasoning: logged costs are the actual costs, invoice third party costs are
what we passed on to the customer (sometimes the offered estimate). If more was
logged than invoiced, the excess is probably not invoiced yet and has to be
subtracted. If less was logged, the invoices know about costs which weren't
logged (or overestimate them), which is pessimistic and fine.

This is still conservative: the result is never more optimistic than
subtracting either source alone. It fixes project A (→ ~60'000) and all of the
projects above without any data entry.

What it doesn't catch: costs of a not yet invoiced project phase, when an
earlier phase's invoices overestimated their third party costs. That
overestimation compensates the missing costs. Acceptable for an estimate.

Implement it once in a helper (e.g. `third_party_costs(projects)` →
`{project_id: amount}`) used by both `squeeze_data` and `project_gross_margin`.

#### b) Correct third party costs on invoices after the fact

Some cases need a human, e.g. third party costs entered wrongly on an invoice
which has already been sent. Example: an invoice of project B carries third
party costs which are almost entirely the campaign website package price
(internal work, see problem 2). The logged cost has already been
corrected to 0.00 third party costs, but the invoice can't be.

`Invoice.third_party_costs` is only used for statistics, so changing it after
the fact doesn't touch anything the customer or the accounting sees. The fix
belongs at the source, not in a separate correction:

- *Fixed amount* and *down payment* invoices: already possible. The field is
  editable directly on the invoice, even when it is frozen (it is in the
  whitelist in `InvoiceForm`, and changing it doesn't trigger the "are you
  sure" warning).
- *Services* invoices: not possible. The invoice's value is computed from its
  services (field disabled), and `Service.allow_update` refuses any change
  once the invoice isn't in preparation anymore.

Change for services invoices:

- `Service.allow_update` allows updates of services on invoices which aren't
  in preparation anymore, including frozen ones. `allow_delete` stays as it
  is. Everyone who can edit invoices may do this, as with fixed amount
  invoices today.
- In that case `ServiceForm` disables all fields except `third_party_costs`
  and says why ("This invoice has already been sent, only the third party
  costs can be changed.").
- Saving the service saves the invoice, which recomputes `third_party_costs`
  from the services. `subtotal` and the totals are recomputed too but can't
  change since the other fields are disabled. A test should verify that.
- Optional convenience: when a logged cost linked to an invoice service
  (`invoice_service`) changes its third party costs, offer to update the
  service. Not automatically: invoice services created from the offer contain
  the offered amounts, not the sum of the logged costs.

With a), b) and the warning in c) a separate correction model isn't needed for
now. If cases show up which can't be fixed on the invoices (e.g. margin which
belongs to another project, which is what `BudgetTransfer` is for), a
`GrossMarginCorrection(project, amount, description, created_by, created_at)`
added to `gross_margin` like the budget adjustment would be the fallback.

The more thorough fix, linking logbook entries to fixed amount invoices, is
described in `specs/invoice-logbook-linking.md`.

#### c) Finding such cases

Show a warning when invoices and logbook disagree a lot about third party
costs on a project:

```
invoiced_3pc = Σ Invoice.third_party_costs
logged_3pc   = Σ LoggedCost.third_party_costs
warn if abs(invoiced_3pc - logged_3pc) > max(500, 10% of the larger value)
```

- In the profitability modal on the project page: "Third party costs on
  invoices (X) and in the logbook (Y) differ. The larger value is used."
- In the squeeze report: a list of projects with such a difference, sorted by
  the difference, with links to the projects. Covers both directions: project A
  (fixed invoices, invoiced and logged third party costs about equal → no
  warning anymore after a), but the big unlinked amount could still be
  listed) and project B (far more on the invoices than logged → the package
  price shows up).

Thresholds to be tuned against the production data.

---

## 3. Problem 2: Work on 0.-/h services gets no margin

### What happens in project B

The campaign website is sold as a package price (a service with a fixed
cost and no hours). The work is logged on separate services for development,
design and project management with an hourly rate of 0.00, ~140h in total,
~35h of them by one developer.

- The project's margin (~125'000, from projected invoices) is divided by all
  ~800 hours, including those ~140h. So the hours *do* lower the project
  rate.
- But the attribution weights those hours with 0, so the whole period slice
  goes to the people working on services with a rate. The developers get
  0.-, the others get ~190.-/h instead of ~155.-/h.

The same pattern exists on other campaign projects (another campaign
has ~40h on a 0.00 development service). 0.00 is also used on all internal
projects (thousands of hours per year), but those have no margin, so the
weighting doesn't matter there.

### Proposed fix

Treat a rate of 0.00 like a missing rate in the attribution weight:

```python
Coalesce(NullIf(F("service__effort_rate"), Value(Z2)), Value(BASE_HOURLY_RATE))
```

and count those hours in `hours_rate_unknown` as well ("hours at default
rate"), so it stays visible.

For project B (all time) that gives the developer with ~35h roughly
35h × 150 / Σ weighted × 125'000 ≈ 4'500.- (~130.-/h); the others drop from
~190.-/h to ~160.-/h. The project's total margin and rate don't change.

Rationale: the rate weighting exists to credit more valuable work (strategy
at a higher rate than production), not to drop work entirely. A rate of
0.00 on a customer project means "paid for elsewhere" (package price, goodwill)
far more often than "worth nothing". Goodwill hours already lower the project
rate for everyone; there is no reason to additionally take them away from the
person who did the work.

Variant: fall back to the person's `specialist_field.expected_hourly_rate`
instead of the flat 150.-/h. Slightly fairer between specialist fields, but
it makes the weight depend on who logged the hours instead of on what was
done. Not recommended for now.

Not proposed: linking the 0.-/h services to the package price service which
pays for them. Precise, but needs data entry on every campaign project, and
the fallback rate gets close enough.

### Related: package price as third party costs

In project B the package price ended up as third party costs on an invoice,
so it is not part of the margin at all, while the ~140h it paid for are. If the package price is internal work it shouldn't be third
party costs. This was a mistake; the logged cost has already been corrected,
the invoice can be corrected once 2b) is implemented. `invoiced` then ends up
just above the projected margin, so the rate only goes from ~155.-/h to
~158.-/h. If the projected invoices were entered without the package price as
well, they should get it too (~175.-/h); the project is still open, so the
projected margin still counts.

---

## 4. Implementation order

Each step is one commit, with a test reproducing the problem first.

1. Rename `EXPECTED_AVERAGE_HOURLY_RATE` to `BASE_HOURLY_RATE`.
2. Zero rate falls back to the base rate in the attribution weight
   (`squeeze_data`), counted as "hours at default rate".
3. `max(invoiced, logged)` third party costs helper, used by `squeeze_data`
   and `project_gross_margin`. Update the explanation in
   `projects/project_profitability.html`.
4. Allow changing the third party costs of services on sent and frozen
   invoices.
5. Third party cost mismatch warning in the profitability modal and the
   squeeze report.

Update the profitability conventions in `AGENTS.md` after 2 and 3.

Linking logbook entries to fixed amount invoices, which would avoid most of
problem 1 at the source, is specified separately in
`specs/invoice-logbook-linking.md`.
