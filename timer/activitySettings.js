import React from "react"

import {COLORS} from "./colors.js"

export const ActivitySettings = ({
  color,
  setColor,
  removeActivity,
  resetActivity,
}) => (
  <div className="activity-settings">
    <div className="activity-color-chooser">
      {COLORS.map(c => (
        <label key={c} style={{backgroundColor: c}}>
          <input
            type="radio"
            name="color"
            value={c}
            selected={c == color}
            onClick={() => setColor(c)}
          />
        </label>
      ))}
    </div>
    <div className="d-flex justify-content-between">
      <button
        className="btn btn-danger"
        type="button"
        onClick={() => removeActivity()}
      >
        Remove
      </button>
      <button
        className="btn btn-warning"
        type="button"
        onClick={() => resetActivity()}
      >
        Reset
      </button>
    </div>
  </div>
)
