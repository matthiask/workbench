from decimal import Decimal


def nice_step(maximum, ticks=4):
    """A round step (1, 2, 2.5 or 5 times a power of ten) dividing ``maximum``
    into about ``ticks`` parts"""
    raw = Decimal(maximum) / ticks
    magnitude = Decimal(10) ** (len(str(int(raw))) - 1)
    if raw < 1:
        magnitude = Decimal(10) ** raw.adjusted()
    return next(
        step * magnitude
        for step in map(Decimal, ("1", "2", "2.5", "5", "10"))
        if step * magnitude >= raw
    )


WIDTH, LEFT, RIGHT, TOP, BOTTOM = 960, 64, 8, 12, 28


def _bar(x, width, y0, y1):
    """A bar from ``y0`` (the baseline side) to ``y1``, with rounded corners
    at the end away from the baseline"""
    radius = min(2, width / 2, abs(y1 - y0))
    sign = 1 if y1 < y0 else -1
    end = y1 + sign * radius
    return (
        f"M{x:.1f},{y0:.1f}V{end:.1f}"
        f"Q{x:.1f},{y1:.1f} {x + radius:.1f},{y1:.1f}"
        f"H{x + width - radius:.1f}"
        f"Q{x + width:.1f},{y1:.1f} {x + width:.1f},{end:.1f}"
        f"V{y0:.1f}Z"
    )


def bar_chart(
    labels, *, bars=(), lines=(), fmt=str, axis_fmt=None, height=280, maximum=None
):
    """Geometry of a chart with stacked bars and lines over categories

    ``bars`` and ``lines`` are lists of dicts with a ``label``, ``values``
    (one per category, ``None`` leaves out a point of a line) and a CSS
    ``color`` class, lines optionally ``dashed``. Series with an empty label
    are left out of the legend and the tooltips. ``fmt`` formats values for
    the tooltips and ``axis_fmt`` (``fmt`` by default) for the axis."""
    axis_fmt = axis_fmt or fmt
    labels = list(labels)
    values = {
        id(series): [
            float(value) if value is not None else None
            for value in [*series["values"], *[None] * len(labels)][: len(labels)]
        ]
        for series in (*bars, *lines)
    }

    stacks = [[0.0, 0.0] for _label in labels]  # negative and positive totals
    for series in bars:
        for stack, value in zip(stacks, values[id(series)], strict=True):
            if value:
                stack[value > 0] += value
    extremes = [
        *(value for stack in stacks for value in stack),
        *(
            value
            for series in lines
            for value in values[id(series)]
            if value is not None
        ),
        0.0,
    ]
    top, bottom = max(extremes), min(extremes)
    if maximum is not None:
        top = maximum
    step = float(nice_step(max(top - bottom, 1)))
    top = step * -(-top // step) if maximum is None else top
    # Small negative values only extend the plot a bit, ticks stay round
    first_tick = -step * (-bottom // step) + 0.0  # Avoid -0.0
    if top <= bottom:
        top = bottom + step

    plot = WIDTH - LEFT - RIGHT
    band = plot / max(len(labels), 1)

    def y(value):
        return TOP + (height - TOP - BOTTOM) * (top - value) / (top - bottom)

    def center(index):
        return LEFT + band * (index + 0.5)

    bar_width = min(band * 0.7, 36)
    stacks = [[0.0, 0.0] for _label in labels]
    bar_series = []
    for series in bars:
        paths = []
        for index, value in enumerate(values[id(series)]):
            if not value:
                continue
            stack = stacks[index]
            start = stack[value > 0]
            stack[value > 0] += value
            paths.append(
                _bar(
                    center(index) - bar_width / 2, bar_width, y(start), y(start + value)
                )
            )
        bar_series.append({"color": series["color"], "path": "".join(paths)})

    line_series = []
    for series in lines:
        path = []
        for index, value in enumerate(values[id(series)]):
            if value is not None:
                path.append(f"{'L' if path else 'M'}{center(index):.1f},{y(value):.1f}")
        line_series.append({
            "color": series["color"],
            "dashed": series.get("dashed", False),
            "path": "".join(path),
        })

    every = -(-len(labels) // 12) or 1
    ticks = round((top - first_tick) / step)
    return {
        "width": WIDTH,
        "height": height,
        "left": LEFT,
        "right": WIDTH - RIGHT,
        "bottom": height - BOTTOM,
        "zero": f"{y(0):.1f}",
        "legend": [
            {"label": series["label"], "color": series["color"], "kind": "bar"}
            for series in bars
        ]
        + [
            {
                "label": series["label"],
                "color": series["color"],
                "kind": "dashed" if series.get("dashed") else "line",
            }
            for series in lines
            # Series without a label (e.g. a second limit) aren't repeated
            if series["label"]
        ],
        "bars": bar_series,
        "lines": line_series,
        "y_ticks": [
            {"y": f"{y(value):.1f}", "label": axis_fmt(Decimal(str(value)))}
            for value in (first_tick + step * i for i in range(ticks + 1))
        ],
        "x_ticks": [
            {"x": f"{center(index):.1f}", "label": label}
            for index, label in enumerate(labels)
            if index % every == 0
        ],
        "columns": [
            {
                "x": f"{LEFT + band * index:.1f}",
                "width": f"{band:.1f}",
                "title": "\n".join([
                    str(label),
                    *(
                        f"{series['label']}: {fmt(Decimal(str(values[id(series)][index])))}"
                        for series in (*bars, *lines)
                        if values[id(series)][index] is not None and series["label"]
                    ),
                ]),
            }
            for index, label in enumerate(labels)
        ],
    }
