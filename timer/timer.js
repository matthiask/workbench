import React from "react"
import {connect} from "react-redux"

import {Activity} from "./activity.js"
import {CreateActivity} from "./createActivity.js"

export const Timer = connect(({activities}) => ({activities}))(
  ({activities}) => (
    <>
      <CreateActivity />
      <div className="activity-list">
        {Object.values(activities).map(activity => (
          <Activity key={activity.id} activity={activity} />
        ))}
      </div>
    </>
  )
)
