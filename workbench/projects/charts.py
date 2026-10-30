import datetime as dt
from decimal import Decimal
from itertools import accumulate

from workbench.invoices.models import Invoice
from workbench.tools.formats import Z2, currency, local_date_format


WIDTH, HEIGHT = 720, 260
LEFT, RIGHT, TOP, BOTTOM = 72, 96, 16, 28


def _nice_step(maximum, ticks=4):
    raw = maximum / ticks
    magnitude = Decimal(10) ** (len(str(int(raw))) - 1)
    return next(
        step * magnitude
        for step in map(Decimal, ("1", "2", "2.5", "5", "10"))
        if step * magnitude >= raw
    )


def _months_between(first, last):
    month = first.replace(day=1)
    while month <= last:
        yield month
        month = (month + dt.timedelta(days=32)).replace(day=1)


def projected_vs_invoiced_chart(project, *, today=None):
    """Geometry of a step line chart of the cumulative projected and the
    cumulative invoiced gross margin (invoices minus their third party costs),
    or ``None`` if there is nothing to draw"""
    today = today or dt.date.today()
    series = {
        "projected": [
            (pi.invoiced_on, pi.gross_margin, pi.description)
            for pi in sorted(
                project.projected_invoices.all(), key=lambda pi: pi.invoiced_on
            )
        ],
        "invoiced": [
            (
                invoice.invoiced_on,
                invoice.total_excl_tax - (invoice.third_party_costs or Z2),
                invoice.title,
            )
            for invoice in Invoice.objects
            .invoiced()
            .filter(project=project)
            .order_by("invoiced_on", "pk")
        ],
    }
    days = [day for entries in series.values() for day, _amount, _text in entries]
    if not days:
        return None

    first, last = min(days), max([*days, today])
    first = first.replace(day=1)
    span = max((last - first).days, 1)
    totals = {
        key: list(accumulate(amount for _day, amount, _text in entries))
        for key, entries in series.items()
    }
    maximum = max(total for values in totals.values() for total in values)
    step = _nice_step(max(maximum, Decimal(1)))
    top = step * (int(maximum / step) + 1)

    def x(day):
        return LEFT + (WIDTH - LEFT - RIGHT) * (day - first).days / span

    def y(value):
        return TOP + (HEIGHT - TOP - BOTTOM) * (1 - float(value) / float(top))

    def build(key, *, until):
        entries, values = series[key], totals[key]
        points = []
        path = [f"M{x(first):.1f},{y(0):.1f}"]
        for (day, amount, text), total in zip(entries, values, strict=True):
            path.append(f"H{x(day):.1f}V{y(total):.1f}")
            points.append({
                "x": f"{x(day):.1f}",
                "y": f"{y(total):.1f}",
                "total": total,
                "title": f"{local_date_format(day)}: +{currency(amount)}"
                f" = {currency(total)}" + (f"\n{text}" if text else ""),
            })
        path.append(f"H{x(until):.1f}")
        end = values[-1] if values else Z2
        return {
            "path": "".join(path),
            "points": points,
            "end": currency(end),
            "end_y": y(end),
        }

    projected = build("projected", until=last)
    # Nothing has been invoiced in the future yet
    invoiced = build("invoiced", until=min(today, last))
    # Keep the end labels apart
    upper, lower = sorted([projected, invoiced], key=lambda line: line["end_y"])
    if (gap := lower["end_y"] - upper["end_y"]) < 14:
        upper["end_y"] -= (14 - gap) / 2
        lower["end_y"] += (14 - gap) / 2
    for line in (projected, invoiced):
        line["end_y"] = f"{line['end_y']:.1f}"

    months = list(_months_between(first, last))
    every = max(1, len(months) // 6)
    return {
        "width": WIDTH,
        "height": HEIGHT,
        "left": LEFT,
        "right": WIDTH - RIGHT,
        "bottom": HEIGHT - BOTTOM,
        "label_x": WIDTH - RIGHT + 8,
        "projected": projected,
        "invoiced": invoiced,
        "y_ticks": [
            {"y": f"{y(value):.1f}", "label": currency(value)}
            for value in [step * i for i in range(int(top / step) + 1)]
        ],
        "x_ticks": [
            {"x": f"{x(month):.1f}", "label": month.strftime("%m.%Y")}
            for month in months[::every]
        ],
        "today_x": f"{x(today):.1f}" if first <= today <= last else None,
    }
