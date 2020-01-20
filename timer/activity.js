import React, {useState, useEffect} from "react"
import Draggable from "react-draggable"
import {connect} from "react-redux"
import Select from "react-select"
import AsyncSelect from "react-select/async"

import {fetchProjects, fetchServices, openForm, sendLogbook} from "./actions.js"
import {ActivitySettings} from "./activitySettings.js"
import {COLORS} from "./colors.js"
import {gettext, OUTCOME} from "./i18n.js"
import {clamp, prettyDuration, timestamp} from "./utils.js"
import * as icons from "./icons.js"

const createUpdater = ({id, dispatch}) => fields =>
  dispatch({
    type: "UPDATE_ACTIVITY",
    id,
    fields,
  })

const analyze = (activity, current) => {
  const isActive = current && current.id == activity.id
  const seconds = Math.ceil(
    activity.seconds + (isActive ? timestamp() - current.startedAt : 0)
  )
  const isReady =
    activity.description &&
    activity.description.length &&
    activity.project &&
    activity.service &&
    seconds > 0

  return {isActive, seconds, isReady}
}

export const Activity = connect((state, ownProps) => ({
  ...ownProps,
  current: state.current,
  projects: state.projects,
}))(({activity, current, projects, dispatch}) => {
  const dispatchUpdate = createUpdater({id: activity.id, dispatch})

  // Precondition check
  if (COLORS.indexOf(activity.color) === -1) {
    dispatchUpdate({color: COLORS[Math.floor(Math.random() * COLORS.length)]})
  }

  // State vars
  const [showSettings, setShowSettings] = useState(false)
  const [services, setServices] = useState([])

  // Analyze
  const {isActive, isReady, seconds} = analyze(activity, current)

  // Update each second if active
  const [, updateState] = useState()
  useEffect(() => {
    if (!isActive) return
    const interval = setInterval(() => updateState({}), 1000)
    return () => clearInterval(interval)
  }, [isActive])

  // Fill services dropdown
  useEffect(() => {
    if (!activity.project) return
    fetchServices(activity.project.value).then(data => setServices(data))
  }, [activity.project])

  const activityTitle = activity.project
    ? activity.project.label.replace(/^[-0-9\s]+/, "")
    : gettext("Activity")

  return (
    <Draggable
      handle=".js-drag-handle"
      bounds="parent"
      defaultPosition={{
        x: clamp(activity.left, 0, window.innerWidth - 300),
        y: clamp(activity.top, 0, window.innerHeight - 300),
      }}
      onStop={(e, data) =>
        dispatchUpdate({
          left: data.x,
          top: data.y,
        })
      }
    >
      <form
        className={`activity ${isActive ? "is-active" : ""} card px-2 py-2`}
        style={{backgroundColor: activity.color}}
      >
        <div
          className="py-2 px-2 text-truncate js-drag-handle"
          title={activityTitle}
        >
          {activityTitle}
        </div>
        <div className="activity-body">
          <div className="form-group">
            <div className="input-group input-group-sm">
              <AsyncSelect
                className="select"
                classNamePrefix="select"
                defaultOptions={projects}
                loadOptions={async (inputValue, callback) => {
                  callback(await fetchProjects(inputValue))
                }}
                onChange={value => {
                  dispatchUpdate({project: value, service: null})
                  setServices([])
                }}
                placeholder={gettext("Select or search project...")}
                value={activity.project}
              />
              {activity.project && (
                <div className="input-group-append">
                  <a
                    href={`/projects/${activity.project.value}/`}
                    className="input-group-text"
                  >
                    {icons.arrow}
                  </a>
                </div>
              )}
            </div>
          </div>
          <div className="form-group">
            <Select
              className="select"
              classNamePrefix="select"
              isDisabled={!services.length}
              options={services}
              onChange={row => {
                dispatchUpdate({service: row})
              }}
              placeholder={
                services.length
                  ? gettext("Select service...")
                  : activity.project
                  ? gettext("No services available")
                  : gettext("No project selected")
              }
              value={activity.service}
            />
          </div>
          <div className="form-group">
            <textarea
              className="form-control"
              rows="2"
              value={activity.description}
              onChange={e => dispatchUpdate({description: e.target.value})}
              placeholder={OUTCOME}
            />
          </div>
          <div className="d-flex align-items-center justify-content-between">
            <div className="activity-duration pl-2">
              {prettyDuration(seconds)}
            </div>
            <div>
              <button
                className="btn btn-light btn-sm"
                type="button"
                onClick={() => setShowSettings(!showSettings)}
                title={gettext("Settings")}
              >
                {icons.cog}
              </button>
              <button
                className={`btn btn-sm ml-2 ${
                  isActive ? "btn-warning" : "btn-light"
                }`}
                type="button"
                onClick={() =>
                  dispatch({
                    type: isActive ? "STOP" : "START",
                    id: activity.id,
                    current,
                  })
                }
              >
                {isActive ? icons.pause : icons.play}
              </button>
              <button
                className="btn btn-sm ml-2 btn-light"
                disabled={!activity.project}
                type="button"
                onClick={() =>
                  openForm(dispatch, {
                    activity,
                    current,
                    seconds,
                  })
                }
                title={gettext("Open logged hours form")}
              >
                {icons.pen}
              </button>
              <button
                className={`btn btn-sm ml-2 ${
                  isReady ? "btn-success" : "btn-light"
                }`}
                disabled={!activity.project || !isReady}
                type="button"
                onClick={() =>
                  sendLogbook(dispatch, {
                    activity,
                    current,
                    seconds,
                  })
                }
                title={gettext("Send to logbook")}
              >
                {icons.arrow}
              </button>
            </div>
          </div>
        </div>
        {showSettings ? (
          <ActivitySettings
            color={activity.color}
            setColor={color => {
              dispatchUpdate({color})
              setShowSettings(false)
            }}
            removeActivity={() => {
              dispatch({type: "REMOVE_ACTIVITY", id: activity.id})
            }}
            resetActivity={() => {
              if (isActive) dispatch({type: "STOP", current})
              dispatchUpdate({seconds: 0})
              setShowSettings(false)
            }}
          />
        ) : null}
      </form>
    </Draggable>
  )
})
