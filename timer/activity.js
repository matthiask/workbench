import React, {useState, useEffect} from "react"
import Draggable from "react-draggable"
import {connect} from "react-redux"
import Select from "react-select"
import AsyncSelect from "react-select/async"

import {clamp, prettyDuration, timestamp, containsJSON} from "./utils.js"
import {endpointUrl} from "./endpoints.js"

const fetchProjects = async q => {
  const url = endpointUrl({name: "projects", urlParams: [q]})
  const response = await fetch(url, {credentials: "include"})
  if (containsJSON(response)) {
    const data = await response.json()
    return data.results
  }
  return []
}

const fetchServices = async project => {
  const url = endpointUrl({name: "services", urlParams: [project]})
  return fetch(url, {credentials: "include"})
}

const COLORS = [
  "#ffffff", // white
  "#f28b82", // red
  "#fbbc04", // orange
  "#fff475", // yellow
  "#ccff90", // green
  "#a7ffeb", // teal
  "#cbf0f8", // blue
  "#aecbfa", // dark blue
  "#d7aefb", // purple
  "#fdcfe8", // pink
  "#e6c9a8", // brown
  "#e8eaed", // gray
]

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
  const {
    description,
    seconds,
    id,
    top,
    left,
    color,
    project,
    service,
  } = activity
  const [showSettings, setShowSettings] = useState(false)
  const [services, setServices] = useState([])

  useEffect(() => {
    if (!project) return

    fetchServices(project.value)
      .then(response => {
        if (containsJSON(response)) return response.json()

        throw Error("Unable to load services for project")
      })
      .then(data => {
        setServices(
          data.services.map(row => ({
            label: row[1],
            value: row[0],
          }))
        )
      })
  }, [project])

  const update = createUpdater({activity: id, dispatch})

  const isActive = current && current.activity == id
  const mySeconds = Math.ceil(
    seconds + (isActive ? timestamp() - current.startedAt : 0)
  )

  const [, updateState] = useState()
  useEffect(() => {
    if (!isActive) return
    const interval = setInterval(() => updateState({}), 1000)
    return () => clearInterval(interval)
  }, [isActive])

  if (COLORS.indexOf(color) === -1) {
    update({color: COLORS[Math.floor(Math.random() * COLORS.length)]})
  }

  const settingsPanel = showSettings ? (
    <div className="activity-settings">
      <div className="activity-color-chooser">
        {COLORS.map(c => (
          <label key={c} style={{backgroundColor: c}}>
            <input
              type="radio"
              name="color"
              value={c}
              selected={c == color}
              onClick={() => {
                update({color: c})
                setShowSettings(false)
              }}
            />
          </label>
        ))}
      </div>
      <div className="d-flex justify-content-between">
        <button
          className="btn btn-danger"
          type="button"
          onClick={() => {
            dispatch({type: "REMOVE_ACTIVITY", activity: id})
          }}
        >
          Remove
        </button>
        <button
          className="btn btn-warning"
          type="button"
          onClick={() => {
            dispatch({type: "STOP"})
            update({seconds: 0})
            setShowSettings(false)
          }}
        >
          Reset
        </button>
      </div>
    </div>
  ) : null

  const isReady =
    description && description.length && mySeconds > 0 && project && service

  return (
    <Draggable
      handle=".js-drag-handle"
      bounds="parent"
      defaultPosition={{
        x: clamp(left, 0, window.innerWidth - 300),
        y: clamp(top, 0, window.innerHeight - 300),
      }}
      onStop={(e, data) =>
        update({
          left: data.x,
          top: data.y,
        })
      }
    >
      <form
        className={`activity ${isActive ? "is-active" : ""} card px-2 py-2`}
        style={{backgroundColor: color}}
      >
        <div className="py-2 px-2 d-flex align-items-center justify-content-between js-drag-handle">
          <h5>Aktivität</h5>
          <button
            className="btn btn-outline-secondary btn-sm"
            type="button"
            onClick={() => setShowSettings(!showSettings)}
          >
            &#x2056;
          </button>
        </div>
        <div className="activity-body">
          {settingsPanel}
          <div className="form-group">
            <AsyncSelect
              className="select"
              classNamePrefix="select"
              defaultOptions={projects}
              loadOptions={async (inputValue, callback) => {
                callback(await fetchProjects(inputValue))
              }}
              onChange={value => {
                update({project: value})
                setServices([])
              }}
              placeholder={project ? project.label : ""}
            />
          </div>
          <div className="form-group">
            <Select
              className="select"
              classNamePrefix="select"
              options={services}
              onChange={row => {
                update({service: row})
              }}
              placeholder={service && service.label}
            />
          </div>
          <div className="form-group">
            <textarea
              className="form-control"
              rows="2"
              value={description}
              onChange={e => update({description: e.target.value})}
              placeholder="Was willst Du erreichen?"
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
                      activity: id,
                      current,
                    })
                  }
                }}
              >
                {isActive ? "Pause" : "Start"}
              </button>
              {project ? (
                <button
                  className={`btn ${
                    isReady ? "btn-success" : "btn-secondary"
                  } ml-2`}
                  type="button"
                  onClick={() => {
                    const url = endpointUrl({
                      name: "createHours",
                      urlParams: [project.value],
                    })
                    const fd = new URLSearchParams()
                    fd.append("project", project.value)
                    if (service) fd.append("service", service.value)
                    fd.append("description", description)
                    fd.append("hours", Math.ceil(mySeconds / 360) / 10)
                    fd.append(
                      "date",
                      new Date().toISOString().replace(/T.*/, "")
                    )

                    const finalUrl = `${url}?${fd.toString()}`
                    console.log(finalUrl)

                    dispatch({type: "STOP", current})
                    dispatch({type: "MODAL_ACTIVITY", activity: id})
                    window.openModalFromUrl(finalUrl)

                    /*
                  if (response.status == 200) {
                    window.initModal(await response.text())
                  } else if (response.status == 201) {
                    // created!
                    update({
                      description: "",
                      seconds: "",
                    })
                  } else {
                    alert("WTF!")
                  }
                  */
                  }}
                >
                  Open
                </button>
              ) : null}
            </div>
          </div>
        </div>
      </form>
    </Draggable>
  )
})
