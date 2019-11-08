import React from "react"
import {Provider, connect} from "react-redux"

import {Activity} from "./activity.js"
import {CreateActivity} from "./createActivity.js"

const ActivityList = connect(({activities}) => ({activities}))(
  ({activities}) => (
    <div className="activity-list">
      {activities.map(activity => (
        <Activity key={activity.id} activity={activity} />
      ))}
    </div>
  )
)

export const Timer = ({store}) => {
  return (
    <Provider store={store}>
      <nav className="navbar navbar-light bg-light">
        <span className="navbar-brand">Timer</span>
        <CreateActivity />
      </nav>
      <ActivityList />
    </Provider>
  )
}
