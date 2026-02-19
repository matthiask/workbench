import { useEffect, useRef } from "react"

import { gettext } from "./i18n.js"

export const ActivitySettings = ({
  title,
  color,
  otherColors,
  dispatchUpdate,
  closeSettings,
  removeActivity,
  resetActivity,
}) => {
  const ref = useRef()
  const colorRef = useRef()

  useEffect(() => {
    const dismissColorPicker = () =>
      colorRef.current?.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      )
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        dismissColorPicker()
        closeSettings()
      }
    }
    document.addEventListener("mousedown", handler)
    return () => {
      dismissColorPicker()
      document.removeEventListener("mousedown", handler)
    }
  }, [closeSettings])

  const colors = ["#ffffff", ...otherColors.filter((c) => c !== "#ffffff")]
  return (
    <div className="activity-settings" ref={ref}>
      <div className="form-group">
        <input
          type="text"
          className="activity-title form-control"
          value={title}
          placeholder="Titel"
          onChange={(e) => dispatchUpdate({ title: e.target.value })}
        />
      </div>
      <div className="form-group">
        <input
          ref={colorRef}
          type="color"
          className="form-control form-control-color w-100"
          value={color}
          onChange={(e) => dispatchUpdate({ color: e.target.value })}
        />
      </div>
      <div className="activity-color-chooser">
        {colors.map((c) => (
          <label
            key={c}
            className={c === color ? "checked" : ""}
            style={{ backgroundColor: c }}
            title={c}
          >
            <input
              type="radio"
              name="color"
              value={c}
              onClick={() => dispatchUpdate({ color: c })}
            />
          </label>
        ))}
      </div>

      <div className="d-flex mt-3">
        <button
          className="btn btn-sm btn-primary"
          type="button"
          onClick={closeSettings}
        >
          {gettext("OK")}
        </button>
        <button
          className="btn btn-sm btn-danger ms-auto me-1"
          type="button"
          onClick={() => removeActivity()}
        >
          {gettext("Remove")}
        </button>
        <button
          className="btn btn-sm btn-warning"
          type="button"
          onClick={() => resetActivity()}
        >
          {gettext("Reset")}
        </button>
      </div>
    </div>
  )
}
