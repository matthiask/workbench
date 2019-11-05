import React from "react"
import {connect} from "react-redux"

import {Activity} from "./activity.js"

export const Activities = connect(({activities}) => ({activities}))(
  ({activities}) => (
    <div className="activity-list">
      {activities.map((activity, idx) => (
        <Activity key={idx} {...activity} />
      ))}
    </div>
  )
)
