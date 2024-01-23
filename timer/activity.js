import React, { useState, useEffect } from "react"
import Draggable from "react-draggable"
import { connect } from "react-redux"
import Select from "react-select"
import AsyncSelect from "react-select/async"

import {
  fetchProjects,
  fetchServices,
  openForm,
  overwriteSeconds,
  sendLogbook,
} from "./actions.js"
import { ActivitySettings } from "./activitySettings.js"
import { gettext, OUTCOME } from "./i18n.js"
import { clamp, prettyDuration } from "./utils.js"
import * as icons from "./icons.js"

const createUpdater =
  ({ id, dispatch }) =>
  (fields) =>
    dispatch({
      type: "UPDATE_ACTIVITY",
      id,
      fields,
    })

export const Activity = connect((state, ownProps) => ({
  activity: ownProps.activity,
  current: state.current,
  projects: state.projects,
}))(({ activity, current, projects, dispatch }) => {
  const dispatchUpdate = createUpdater({ id: activity.id, dispatch })

  // State vars
  const [showSettings, setShowSettings] = useState(false)
  const [services, setServices] = useState([])

  // Fill services dropdown
  useEffect(() => {
    if (!activity.project) return
    fetchServices(activity.project.value).then((data) => setServices(data))
  }, [activity.project])

  const activityTitle = activity.title || gettext("Activity")

  const isReady =
    activity.description &&
    activity.description.length &&
    activity.project &&
    activity.service &&
    activity.seconds > 0

  return (
    <Draggable
      handle=".js-drag-handle"
      bounds="parent"
      defaultPosition={{
        x:
          10 *
          Math.floor(clamp(activity.left, 0, window.innerWidth - 300) / 10),
        y:
          10 *
          Math.floor(clamp(activity.top, 0, window.innerHeight - 300) / 10),
      }}
      grid={[10, 10]}
      onStop={(e, data) =>
        dispatchUpdate({
          left: data.x,
          top: data.y,
        })
      }
    >
      <form
        className={`activity ${
          activity.isActive ? "is-active" : ""
        } card px-2 py-2`}
        style={{ backgroundColor: activity.color }}
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
                onChange={(value) => {
                  dispatchUpdate({
                    title: value.label.replace(/^[-0-9\s]+/, ""),
                    project: value,
                    service: null,
                  })
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
                    title={gettext("Go to the project")}
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
              isClearable={true}
              isDisabled={!services.length}
              options={services}
              onChange={(service) => dispatchUpdate({ service })}
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
              onChange={(e) => dispatchUpdate({ description: e.target.value })}
              placeholder={OUTCOME}
            />
          </div>
          <div className="d-flex align-items-center justify-content-between">
            <div
              className="activity-duration pl-2"
              onClick={() => overwriteSeconds(dispatch, { activity, current })}
              style={{ cursor: "cell" }}
            >
              {prettyDuration(activity.seconds)}
            </div>
            <div>
              <button
                className={`btn btn-light btn-sm ${
                  showSettings ? "active" : ""
                }`}
                type="button"
                onClick={() => setShowSettings(!showSettings)}
                title={gettext("Settings")}
              >
                {icons.cog}
              </button>
              <button
                className={`btn btn-sm ml-2 ${
                  activity.isActive ? "btn-warning" : "btn-light"
                }`}
                type="button"
                onClick={() =>
                  dispatch({
                    type: activity.isActive ? "STOP" : "START",
                    id: activity.id,
                    current,
                  })
                }
              >
                {activity.isActive ? icons.pause : icons.play}
              </button>
              <button
                className="btn btn-sm ml-2 btn-light"
                disabled={!activity.project}
                type="button"
                onClick={() =>
                  openForm(dispatch, {
                    activity,
                    current,
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
                  })
                }
                title={gettext("Send to logbook")}
              >
                {icons.save}
              </button>
            </div>
          </div>
        </div>
        {showSettings ? (
          <ActivitySettings
            title={activity.title}
            color={activity.color}
            dispatchUpdate={dispatchUpdate}
            closeSettings={() => setShowSettings(false)}
            removeActivity={() => {
              dispatch({ type: "REMOVE_ACTIVITY", id: activity.id })
            }}
            resetActivity={() => {
              if (activity.isActive) dispatch({ type: "STOP", current })
              dispatchUpdate({ seconds: 0 })
              setShowSettings(false)
            }}
          />
        ) : null}
      </form>
    </Draggable>
  )
})
