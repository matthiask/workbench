import React, {useState, useEffect} from "react"
import Draggable from "react-draggable"
import {connect} from "react-redux"
import Select from "react-select"
import AsyncSelect from "react-select/async"

import {fetchProjects, fetchServices} from "./actions.js"
import {ActivitySettings} from "./activitySettings.js"
import {COLORS} from "./colors.js"
import {endpointUrl} from "./endpoints.js"
import {gettext} from "./i18n.js"
import {clamp, prettyDuration, timestamp} from "./utils.js"

const createUpdater = ({activity, dispatch}) => fields =>
  dispatch({
    type: "UPDATE_ACTIVITY",
    activity,
    fields,
  })

export const Activity = connect((state, ownProps) => ({
  ...ownProps,
  current: state.current,
  projects: state.projects,
}))(({activity, current, projects, dispatch}) => {
  const [showSettings, setShowSettings] = useState(false)
  const [services, setServices] = useState([])

  const dispatchUpdate = createUpdater({activity: activity.id, dispatch})

  const isActive = current && current.activity == activity.id
  const mySeconds = Math.ceil(
    activity.seconds + (isActive ? timestamp() - current.startedAt : 0)
  )
  const isReady =
    activity.description &&
    activity.description.length &&
    mySeconds > 0 &&
    activity.project &&
    activity.service

  const [, updateState] = useState()
  useEffect(() => {
    if (!isActive) return
    const interval = setInterval(() => updateState({}), 1000)
    return () => clearInterval(interval)
  }, [isActive])

  if (COLORS.indexOf(activity.color) === -1) {
    dispatchUpdate({color: COLORS[Math.floor(Math.random() * COLORS.length)]})
  }

  useEffect(() => {
    if (!activity.project) return
    ;(async function doFetch() {
      setServices(await fetchServices(activity.project.value))
    })()
  }, [activity.project])

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
        <div className="py-2 px-2 d-flex align-items-center justify-content-between js-drag-handle">
          <h5>{gettext("Activity")}</h5>
          <button
            className="btn btn-outline-secondary btn-sm"
            type="button"
            onClick={() => setShowSettings(!showSettings)}
            title={gettext("Settings")}
          >
            &#x2056;
          </button>
        </div>
        <div className="activity-body">
          {showSettings ? (
            <ActivitySettings
              color={activity.color}
              setColor={color => {
                dispatchUpdate({color})
                setShowSettings(false)
              }}
              removeActivity={() => {
                dispatch({type: "REMOVE_ACTIVITY", activity: activity.id})
              }}
              resetActivity={() => {
                dispatch({type: "STOP"})
                dispatchUpdate({seconds: 0})
                setShowSettings(false)
              }}
            />
          ) : null}
          <div className="form-group">
            <AsyncSelect
              className="select"
              classNamePrefix="select"
              defaultOptions={projects}
              loadOptions={async (inputValue, callback) => {
                callback(await fetchProjects(inputValue))
              }}
              onChange={value => {
                dispatchUpdate({project: value})
                setServices([])
              }}
              placeholder={activity.project ? activity.project.label : ""}
            />
          </div>
          <div className="form-group">
            <Select
              className="select"
              classNamePrefix="select"
              options={services}
              onChange={row => {
                dispatchUpdate({service: row})
              }}
              placeholder={activity.service && activity.service.label}
            />
          </div>
          <div className="form-group">
            <textarea
              className="form-control"
              rows="2"
              value={activity.description}
              onChange={e => dispatchUpdate({description: e.target.value})}
              placeholder={gettext("What do you want to achieve?")}
            />
          </div>
          <div className="d-flex align-items-center justify-content-between">
            <div className="activity-duration pl-2">
              {prettyDuration(mySeconds)}
            </div>
            <div>
              <button
                className={`btn ${
                  isActive ? "btn-warning" : "btn-outline-secondary"
                }`}
                type="button"
                onClick={e => {
                  e.preventDefault()
                  if (isActive) {
                    dispatch({
                      type: "STOP",
                      current,
                    })
                  } else {
                    dispatch({
                      type: "START",
                      activity: activity.id,
                      current,
                    })
                  }
                }}
              >
                {isActive ? gettext("Pause") : gettext("Start")}
              </button>
              {activity.project ? (
                <button
                  className={`btn ${
                    isReady ? "btn-success" : "btn-secondary"
                  } ml-2`}
                  type="button"
                  onClick={() => {
                    const url = endpointUrl({
                      name: "createHours",
                      urlParams: [activity.project.value],
                    })
                    const fd = new URLSearchParams()
                    if (activity.service)
                      fd.append("service", activity.service.value)
                    fd.append("description", activity.description)
                    fd.append("hours", Math.ceil(mySeconds / 360) / 10)
                    fd.append(
                      "date",
                      new Date().toISOString().replace(/T.*/, "")
                    )

                    const finalUrl = `${url}?${fd.toString()}`
                    console.log(finalUrl)

                    dispatch({type: "STOP", current})
                    dispatch({type: "MODAL_ACTIVITY", activity: activity.id})
                    window.openModalFromUrl(finalUrl)
                  }}
                >
                  {gettext("Form")}
                </button>
              ) : null}
            </div>
          </div>
        </div>
      </form>
    </Draggable>
  )
})
