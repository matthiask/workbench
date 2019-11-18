import React from "react"
import {connect} from "react-redux"

import {Activity} from "./activity.js"
import {CreateActivity} from "./createActivity.js"
import {gettext} from "./i18n.js"

export const Timer = connect(({activities}) => ({activities}))(
  ({activities}) => (
    <>
      <nav className="navbar navbar-dark bg-primary">
        <span className="navbar-brand">{gettext("Timer")}</span>
        <CreateActivity />
      </nav>
      <div className="activity-list">
        {Object.values(activities).map(activity => (
          <Activity key={activity.id} activity={activity} />
        ))}
      </div>
    </>
  )
)
