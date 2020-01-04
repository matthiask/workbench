import React from "react"
import {connect} from "react-redux"

import {createActivity} from "./actions.js"
import {gettext} from "./i18n.js"

export const CreateActivity = connect()(({dispatch}) => {
  return (
    <button
      className="btn btn-secondary create-activity"
      type="button"
      onClick={() => {
        createActivity(dispatch)
      }}
    >
      +{gettext("Timer")}
    </button>
  )
})
