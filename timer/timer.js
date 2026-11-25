import { useEffect, useLayoutEffect, useRef, useState } from "react"
import { connect } from "react-redux"

import { Activity } from "./activity.js"
import { BreakActivity } from "./breakActivity.js"
import { CreateActivity } from "./createActivity.js"
import { gettext } from "./i18n.js"
import { SelectionContext } from "./movable.js"
import {
  areaBox,
  arrange,
  position,
  prettyDuration,
  timestamp,
} from "./utils.js"

const hours = JSON.parse(document.getElementById("user-hours").textContent)

// Empty space where dragging draws a rectangle to select activities
const isEmptySpace = (el, area) =>
  el === area ||
  el === document.body ||
  el === document.documentElement ||
  el.matches('div[role="main"]')

// Select the activities touched by a rectangle dragged over empty space,
// with Shift added to the selection. A click on empty space or Escape
// clears the selection.
function useRectangleSelection(areaRef, setSelection) {
  const [rectangle, setRectangle] = useState(null)
  useEffect(() => {
    const point = (e) => {
      const area = areaRef.current
      const rect = area.getBoundingClientRect()
      const k = rect.width / area.offsetWidth || 1
      return {
        x: (e.clientX - rect.left) / k,
        y: (e.clientY - rect.top) / k,
      }
    }
    const normalize = (a, b) => ({
      left: Math.min(a.x, b.x),
      top: Math.min(a.y, b.y),
      right: Math.max(a.x, b.x),
      bottom: Math.max(a.y, b.y),
    })

    const onPointerDown = (e) => {
      const area = areaRef.current
      if (e.button !== 0 || !area || !isEmptySpace(e.target, area)) return
      const start = point(e)
      let moved = false
      document.body.classList.add("is-selecting")

      const onPointerMove = (e) => {
        const end = point(e)
        moved ||= Math.hypot(end.x - start.x, end.y - start.y) > 4
        if (moved) setRectangle(normalize(start, end))
      }
      const onPointerUp = (e) => {
        window.removeEventListener("pointermove", onPointerMove)
        window.removeEventListener("pointerup", onPointerUp)
        document.body.classList.remove("is-selecting")
        setRectangle(null)
        if (!moved) {
          setSelection(new Set())
          return
        }
        const r = normalize(start, point(e))
        const ids = [...area.querySelectorAll("[data-activity]")]
          .filter((el) => {
            const b = areaBox(area, el)
            return (
              b.left < r.right &&
              b.right > r.left &&
              b.top < r.bottom &&
              b.bottom > r.top
            )
          })
          .map((el) => el.dataset.activity)
        setSelection((selection) =>
          e.shiftKey ? new Set([...selection, ...ids]) : new Set(ids),
        )
      }
      window.addEventListener("pointermove", onPointerMove)
      window.addEventListener("pointerup", onPointerUp)
    }
    const onKeyDown = (e) => {
      if (e.key === "Escape") setSelection(new Set())
    }

    document.addEventListener("pointerdown", onPointerDown)
    document.addEventListener("keydown", onKeyDown)
    return () => {
      document.removeEventListener("pointerdown", onPointerDown)
      document.removeEventListener("keydown", onKeyDown)
    }
  }, [areaRef, setSelection])
  return rectangle
}

export const Timer = connect(({ activities, current, zoom }) => ({
  activities,
  current,
  zoom,
}))(({ activities, current, zoom, dispatch }) => {
  const areaRef = useRef()
  const [selection, setSelection] = useState(() => new Set())
  const [drag, setDrag] = useState(null)
  const rectangle = useRectangleSelection(areaRef, setSelection)

  // Arrange the selected activities (or all) in rows. Undo is offered until
  // one of them moves.
  // Chrome keeps the page's scrollable size when only the transforms of the
  // activities change (e.g. arranging them), so lay out the area again
  const positions = Object.values(activities)
    .map((a) => `${a.id}:${a.left}:${a.top}`)
    .join()
  useLayoutEffect(() => {
    const area = areaRef.current
    if (!area || !positions) return
    area.style.minWidth = "0px"
    void area.offsetWidth
    area.style.minWidth = ""
  }, [positions])

  const [arranged, setArranged] = useState(null)
  const byId = activities
  const arrangeActivities = () => {
    const area = areaRef.current
    const nodes = [...area.querySelectorAll("[data-activity]")].filter(
      (el) => !selection.size || selection.has(el.dataset.activity),
    )
    if (!nodes.length) return
    const items = nodes.map((el) => {
      const box = areaBox(area, el)
      return {
        id: el.dataset.activity,
        left: box.left,
        top: box.top,
        width: box.right - box.left,
        height: box.bottom - box.top,
      }
    })
    const start = selection.size
      ? {
          left: Math.min(...items.map((i) => i.left)),
          top: Math.min(...items.map((i) => i.top)),
        }
      : { left: 20, top: 20 }
    // Left of the buttons, but with room for at least one activity
    const buttons = document.querySelector(".create-activity")
    const right = Math.max(
      buttons ? areaBox(area, buttons).left - 10 : area.offsetWidth,
      start.left + Math.max(...items.map((i) => i.width)),
    )
    const after = arrange(items, { ...start, right })
    const before = Object.fromEntries(
      items.map(({ id }) => {
        const { x, y } = position(byId[id])
        return [id, { left: x, top: y }]
      }),
    )
    dispatch({ type: "PLACE_ACTIVITIES", positions: after })
    setArranged({ before, after })
  }
  const canUndo =
    arranged &&
    Object.entries(arranged.after).every(([id, place]) => {
      const p = byId[id] && position(byId[id])
      return p && p.x === place.left && p.y === place.top
    })
  const undoArrange = () => {
    dispatch({ type: "PLACE_ACTIVITIES", positions: arranged.before })
    setArranged(null)
  }

  // Update each second if any activity is current
  const [, updateState] = useState()
  useEffect(() => {
    if (!current) return
    const interval = setInterval(() => updateState({}), 1000)
    return () => clearInterval(interval)
  }, [current])

  activities = Object.values(activities).map((activity) => {
    if (!current || current.id !== activity.id) return activity

    const seconds = Math.ceil(
      activity.seconds + timestamp() - current.startedAt,
    )
    return {
      ...activity,
      seconds,
      isActive: true,
    }
  })

  const totalSeconds = Math.ceil(
    activities
      .filter((a) => a.type !== "break")
      .reduce((sum, activity) => sum + activity.seconds, 0),
  )

  const usedColors = [
    ...new Set(activities.map((a) => a.color).filter(Boolean)),
  ]

  return (
    <>
      <CreateActivity
        arrange={canUndo ? undoArrange : arrangeActivities}
        canUndo={canUndo}
        hasSelection={selection.size > 0}
      />
      <div className="total-seconds">
        <span>
          <span className="total-seconds-label">{gettext("Today")}</span>
          {hours.today}
        </span>
        <span>
          <span className="total-seconds-label">{gettext("This week")}</span>
          {hours.week}
        </span>
        <span>
          <span className="total-seconds-label">{gettext("Timer")}</span>
          {prettyDuration(totalSeconds)}
        </span>
      </div>
      <SelectionContext value={{ selection, setSelection, drag, setDrag }}>
        <div className="activity-list" style={{ zoom }} ref={areaRef}>
          {activities.map((activity) =>
            activity.type === "break" ? (
              <BreakActivity
                key={activity.id}
                activity={activity}
                usedColors={usedColors}
              />
            ) : (
              <Activity
                key={activity.id}
                activity={activity}
                usedColors={usedColors}
              />
            ),
          )}
          {rectangle ? (
            <div
              className="activity-selection"
              style={{
                left: rectangle.left,
                top: rectangle.top,
                width: rectangle.right - rectangle.left,
                height: rectangle.bottom - rectangle.top,
              }}
            />
          ) : null}
        </div>
      </SelectionContext>
    </>
  )
})
