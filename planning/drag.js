import { useEffect, useRef } from "react"

const gettext = window.gettext || ((t) => t)
const interpolate =
  window.interpolate ||
  ((fmt, args) => args.reduce((s, a) => s.replace("%s", a), fmt))

// Pointer movement in pixels before a press becomes a drag
const THRESHOLD = 4

const clamp = (min, value, max) => Math.max(Math.min(value, max), min)

// Weeks are ISO dates of mondays, compute in UTC to avoid DST surprises
const addWeeks = (iso, weeks) => {
  const date = new Date(`${iso}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + 7 * weeks)
  return date.toISOString().slice(0, 10)
}

// The planning has no forms, the page may not have set the CSRF cookie
const csrfToken = () =>
  document.querySelector("#planning-root").dataset.csrfToken

// New weeks of planned work while moving it or one of its ranges' edges.
// Weeks outside the visible range are kept or moved along.
export function draggedWeeks(state, delta, mondays) {
  if (state.kind === "move") {
    return state.weeks.map((week) => addWeeks(week, delta))
  }
  const { start, end } = state
  const [from, until] =
    state.kind === "start"
      ? [clamp(0, start + delta, end), end]
      : [start, clamp(start, end + delta, mondays.length - 1)]
  const before = new Set(mondays.slice(start, end + 1))
  return [
    ...new Set([
      ...state.weeks.filter((week) => !before.has(week)),
      ...mondays.slice(from, until + 1),
    ]),
  ].sort()
}

// Pretty description of weeks, e.g. "KW 45–47, 3 weeks, 4.0h per week"
export function describeWeeks(weeks, plannedHours) {
  // ISO week number of a monday: the week of its thursday in that year
  const kw = (iso) => {
    const thursday = new Date(`${iso}T00:00:00Z`)
    thursday.setUTCDate(thursday.getUTCDate() + 3)
    const newYear = Date.UTC(thursday.getUTCFullYear(), 0, 1)
    return 1 + Math.floor((thursday - newYear) / (7 * 864e5))
  }
  const first = kw(weeks[0])
  const last = kw(weeks[weeks.length - 1])
  const parts = [
    first === last
      ? interpolate(gettext("KW %s"), [first])
      : interpolate(gettext("KW %s–%s"), [first, last]),
    weeks.length === 1
      ? gettext("1 week")
      : interpolate(gettext("%s weeks"), [weeks.length]),
  ]
  if (plannedHours) {
    parts.push(
      interpolate(gettext("%sh per week"), [
        (plannedHours / weeks.length).toFixed(1),
      ]),
    )
  }
  return parts.join(", ")
}

/*
 * Dragging in the planning grid:
 *
 * - Pressing on an empty cell in the row of a project, an offer or a
 *   milestone and dragging sideways selects weeks, releasing opens the form
 *   for new planned work with those weeks.
 * - Dragging planned work moves all its weeks, dragging the edges of a bar
 *   makes it longer or shorter. The planned hours stay the same and are
 *   spread over the new weeks.
 *
 * Rows which accept new work contain an element with `data-create-url`,
 * bars of planned work have `data-work-id`, and the edges `data-resize`.
 */
export function usePlanningDrag({
  gridRef,
  data,
  findWork,
  setDrag,
  setStatus,
  reload,
}) {
  const stateRef = useRef(null)
  const suppressClick = useRef(false)

  const mondays = data.weeks.map((week) => week.monday)

  const weekAt = (x) => {
    const ruler = gridRef.current.querySelector("[data-weeks-ruler]")
    const { left, width } = ruler.getBoundingClientRect()
    return clamp(
      0,
      Math.floor(((x - left) / width) * mondays.length),
      mondays.length - 1,
    )
  }

  const finish = () => {
    stateRef.current = null
    document.body.classList.remove("planning-dragging")
  }

  const onPointerDown = (e) => {
    if (data.external_view || e.button !== 0 || e.pointerType === "touch") {
      return
    }

    const bar = e.target.closest("[data-work-id]")
    if (bar) {
      const work = findWork(Number(bar.dataset.workId))
      if (!work) return
      stateRef.current = {
        kind: e.target.closest("[data-resize]")?.dataset.resize || "move",
        work,
        weeks: work.weeks,
        start: Number(bar.dataset.rangeStart),
        end: Number(bar.dataset.rangeEnd),
        index: weekAt(e.clientX),
      }
    } else {
      const zone = document
        .elementsFromPoint(e.clientX, e.clientY)
        .find((el) => el.dataset.createUrl)
      if (!zone) return
      const index = weekAt(e.clientX)
      stateRef.current = {
        kind: "create",
        url: zone.dataset.createUrl,
        row: Number(zone.dataset.row),
        index,
      }
      setDrag({
        kind: "create",
        row: stateRef.current.row,
        from: index,
        to: index,
      })
      // There is no link to click, keep receiving events outside the grid
      gridRef.current.setPointerCapture(e.pointerId)
    }

    Object.assign(stateRef.current, {
      x: e.clientX,
      pointerId: e.pointerId,
      dragging: false,
    })
    // Avoid selecting text and dragging links
    e.preventDefault()
  }

  const onPointerMove = (e) => {
    const state = stateRef.current
    if (!state || e.pointerId !== state.pointerId) return

    if (!state.dragging) {
      if (Math.abs(e.clientX - state.x) < THRESHOLD) return
      state.dragging = true
      gridRef.current.setPointerCapture(e.pointerId)
      document.body.classList.add("planning-dragging")
    }

    const index = weekAt(e.clientX)
    if (state.kind === "create") {
      const from = Math.min(state.index, index)
      const to = Math.max(state.index, index)
      setDrag({ kind: "create", row: state.row, from, to })
      setStatus({
        text: describeWeeks(mondays.slice(from, to + 1)),
        level: "info",
      })
    } else {
      const weeks = draggedWeeks(state, index - state.index, mondays)
      state.newWeeks = weeks
      setDrag({ kind: "work", id: state.work.id, weeks })
      setStatus({
        text: `${state.work.title}: ${describeWeeks(
          weeks,
          Number.parseFloat(state.work.planned_hours),
        )}`,
        level: "info",
      })
    }
  }

  const save = async (work, weeks) => {
    setStatus({ text: gettext("Saving..."), level: "info" })
    try {
      const response = await fetch(`/api/planning/work/${work.id}/`, {
        method: "PATCH",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
        },
        body: JSON.stringify({ weeks }),
      })
      const result = await response.json()
      if (!response.ok) {
        const { detail } = result
        throw new Error(
          (Array.isArray(detail)
            ? detail.map((error) => error.msg).join(" ")
            : detail) || response.statusText,
        )
      }
      await reload()
      setStatus(
        result.warnings?.length
          ? {
              text: result.warnings.map((w) => w.msg).join(" "),
              level: "warning",
            }
          : null,
      )
    } catch (error) {
      setStatus({
        text: interpolate(gettext("Unable to save the planned work: %s"), [
          error.message,
        ]),
        level: "danger",
      })
    }
    setDrag(null)
  }

  const onPointerUp = (e) => {
    const state = stateRef.current
    if (!state || e.pointerId !== state.pointerId) return
    finish()

    if (state.kind === "create") {
      // A simple click selects one week
      const index = state.dragging ? weekAt(e.clientX) : state.index
      const from = Math.min(state.index, index)
      const to = Math.max(state.index, index)
      const params = new URLSearchParams()
      for (const week of mondays.slice(from, to + 1)) {
        params.append("weeks", week)
      }
      const url = state.url
      window.openModalFromUrl(
        `${url}${url.includes("?") ? "&" : "?"}${params.toString()}`,
      )
      setDrag(null)
      setStatus(null)
    } else if (state.dragging) {
      const weeks = state.newWeeks
      if (weeks && weeks.join() !== state.weeks.join()) {
        save(state.work, weeks)
      } else {
        setDrag(null)
        setStatus(null)
      }
    }

    if (state.dragging) suppressClick.current = true
  }

  const cancel = () => {
    if (!stateRef.current) return
    finish()
    setDrag(null)
    setStatus(null)
  }

  // Clicking planned work opens it, but not after dragging it
  const onClickCapture = (e) => {
    if (suppressClick.current) {
      suppressClick.current = false
      e.preventDefault()
      e.stopPropagation()
    }
  }

  // biome-ignore lint/correctness/useExhaustiveDependencies: cancel only uses refs and stable setters
  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key === "Escape") cancel()
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [])

  return {
    onPointerDown,
    onPointerMove,
    onPointerUp,
    onPointerCancel: cancel,
    onClickCapture,
  }
}
