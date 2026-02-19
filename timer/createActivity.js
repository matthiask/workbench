import { connect } from "react-redux"

import { createActivity, createBreak } from "./actions.js"
import { gettext } from "./i18n.js"

export const CreateActivity = connect()(({ dispatch }) => {
  return (
    <div className="create-activity d-flex flex-column gap-1">
      <button
        className="btn btn-secondary"
        type="button"
        onClick={() => createActivity(dispatch)}
      >
        +{gettext("Timer")}
      </button>
      <button
        className="btn btn-secondary"
        type="button"
        onClick={() => createBreak(dispatch)}
      >
        +{gettext("Break")}
      </button>
    </div>
  )
})
