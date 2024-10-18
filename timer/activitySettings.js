import { COLORS } from "./colors.js"
import { gettext } from "./i18n.js"

export const ActivitySettings = ({
  title,
  color,
  dispatchUpdate,
  closeSettings,
  removeActivity,
  resetActivity,
}) => (
  <div className="activity-settings">
    <div className="form-group">
      <input
        type="text"
        className="activity-title form-control"
        value={title}
        onChange={(e) => dispatchUpdate({ title: e.target.value })}
      />
    </div>
    <div className="activity-color-chooser">
      {COLORS.map((c) => (
        <label
          key={c}
          className={c === color ? "checked" : ""}
          style={{ backgroundColor: c }}
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
        className="btn btn-sm btn-danger ml-auto mr-1"
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
