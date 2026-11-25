import { connect } from "react-redux"

import { createActivity, createBreak } from "./actions.js"
import { gettext } from "./i18n.js"
import { ZOOM_LEVELS } from "./reducers.js"

export const CreateActivity = connect(({ zoom }) => ({ zoom }))(
  ({ dispatch, zoom }) => {
    const index = ZOOM_LEVELS.indexOf(zoom)
    const setZoom = (offset) =>
      dispatch({ type: "ZOOM", zoom: ZOOM_LEVELS[index + offset] })
    return (
      <div className="create-activity d-flex flex-column gap-1">
        <button
          className="btn btn-primary"
          type="button"
          onClick={() => createActivity(dispatch)}
        >
          + {gettext("Timer")}
        </button>
        <button
          className="btn btn-quiet"
          type="button"
          onClick={() => createBreak(dispatch)}
        >
          + {gettext("Break")}
        </button>
        <div className="activity-zoom">
          <button
            className="btn btn-quiet"
            type="button"
            disabled={index <= 0}
            onClick={() => setZoom(-1)}
            title={gettext("Smaller")}
            aria-label={gettext("Smaller")}
          >
            −
          </button>
          <span className="activity-zoom-level">{Math.round(zoom * 100)}%</span>
          <button
            className="btn btn-quiet"
            type="button"
            disabled={index >= ZOOM_LEVELS.length - 1}
            onClick={() => setZoom(1)}
            title={gettext("Larger")}
            aria-label={gettext("Larger")}
          >
            +
          </button>
        </div>
      </div>
    )
  },
)
