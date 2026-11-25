import { createContext, useContext, useRef, useState } from "react"
import Draggable from "react-draggable"
import { connect } from "react-redux"

import { dragBounds, position, startAutoScroll } from "./utils.js"

// The selected activities and the offset of those being dragged right now,
// provided by the timer. Not persisted: a selection only lasts until reload.
export const SelectionContext = createContext({
  selection: new Set(),
  setSelection: () => {},
  drag: null,
  setDrag: () => {},
})

// An activity which can be dragged by its title, together with the other
// selected activities if it is selected itself.
export const Movable = connect(({ zoom }) => ({ zoom }))(
  ({
    activity,
    as: Tag = "div",
    className,
    style,
    children,
    dispatch,
    zoom,
  }) => {
    const ref = useRef()
    // The activities being dragged and their offset as last shown. The
    // position passed to onStop can be off by a step of the grid.
    const dragRef = useRef({ ids: [], dx: 0, dy: 0 })
    const [bounds, setBounds] = useState()
    const stopScrollRef = useRef(null)
    const { selection, setSelection, drag, setDrag } =
      useContext(SelectionContext)

    const isSelected = selection.has(activity.id)
    const base = position(activity)
    const offset = drag?.ids.includes(activity.id) ? drag : { dx: 0, dy: 0 }

    return (
      <Draggable
        handle=".js-drag-handle"
        bounds={bounds}
        position={{ x: base.x + offset.dx, y: base.y + offset.dy }}
        grid={[10, 10]}
        scale={zoom}
        nodeRef={ref}
        onStart={(e) => {
          // A text selection would be dragged by the browser itself, which
          // swallows the mouseup and never ends this drag
          e.preventDefault()
          window.getSelection()?.removeAllRanges()
          if (e.shiftKey) {
            const next = new Set(selection)
            if (isSelected) next.delete(activity.id)
            else next.add(activity.id)
            setSelection(next)
            return false
          }
          const area = ref.current.parentElement
          const nodes = isSelected
            ? [...area.querySelectorAll("[data-activity]")].filter((el) =>
                selection.has(el.dataset.activity),
              )
            : [ref.current]
          if (!isSelected) setSelection(new Set())
          dragRef.current = {
            ids: nodes.map((el) => el.dataset.activity),
            dx: 0,
            dy: 0,
          }
          setBounds(dragBounds(ref.current, nodes))
          setDrag(dragRef.current)
          // The drag follows mouse events, repeat the last one after scrolling
          stopScrollRef.current = startAutoScroll((clientX, clientY) =>
            document.dispatchEvent(
              new MouseEvent("mousemove", { clientX, clientY, bubbles: true }),
            ),
          )
        }}
        onDrag={(_e, data) => {
          dragRef.current = {
            ...dragRef.current,
            dx: data.x - base.x,
            dy: data.y - base.y,
          }
          setDrag(dragRef.current)
        }}
        onStop={() => {
          stopScrollRef.current?.()
          stopScrollRef.current = null
          const { ids, dx, dy } = dragRef.current
          if (dx || dy) dispatch({ type: "MOVE_ACTIVITIES", ids, dx, dy })
          setDrag(null)
        }}
      >
        <Tag
          ref={ref}
          data-activity={activity.id}
          className={`${className} ${isSelected ? "is-selected" : ""}`}
          style={style}
        >
          {children}
        </Tag>
      </Draggable>
    )
  },
)
