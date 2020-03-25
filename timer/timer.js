import React, {useEffect, useState} from "react"
import {connect} from "react-redux"

import {Activity} from "./activity.js"
import {CreateActivity} from "./createActivity.js"
import {prettyDuration, timestamp} from "./utils.js"

const hours = JSON.parse(document.getElementById("user-hours").textContent)

export const Timer = connect(({activities, current}) => ({
  activities,
  current,
}))(({activities, current}) => {
  // Update each second if any activity is current
  const [, updateState] = useState()
  useEffect(() => {
    if (!current) return
    const interval = setInterval(() => updateState({}), 1000)
    return () => clearInterval(interval)
  }, [current])

  activities = Object.values(activities).map(activity => {
    if (!current || current.id != activity.id) return activity

    const seconds = Math.ceil(
      activity.seconds + timestamp() - current.startedAt
    )
    return {
      ...activity,
      seconds,
      isActive: true,
      isReady:
        activity.description &&
        activity.description.length &&
        activity.project &&
        activity.service &&
        seconds > 0,
    }
  })

  const totalSeconds = Math.ceil(
    activities.reduce((sum, activity) => sum + activity.seconds, 0)
  )

  return (
    <>
      <CreateActivity />
      <div className="total-seconds">
        Today: {hours.today}
        <br />
        This week: {hours.week}
        <br />
        Timer: {prettyDuration(totalSeconds)}
      </div>
      <div className="activity-list">
        {activities.map(activity => (
          <Activity key={activity.id} activity={activity} />
        ))}
      </div>
    </>
  )
})
