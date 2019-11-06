import React, {useState, useRef, useEffect} from "react"
import Draggable from "react-draggable"
import {connect} from "react-redux"
import Select from "react-select"
import AsyncSelect from "react-select/async"

import {clamp, prettyDuration, timestamp, containsJSON} from "./utils.js"
import {endpointUrl} from "./endpoints.js"

const fetchProjects = q => {
  const url = endpointUrl({name: "projects", urlParams: [q]})
  return fetch(url, {credentials: "include"})
}

const fetchServices = project => {
  const url = endpointUrl({name: "services", urlParams: [project]})
  return fetch(url, {credentials: "include"})
}

export const Activity = connect((state, ownProps) => ({
  ...ownProps,
  current: state.current,
}))(({activity, current, dispatch}) => {
  const {
    description,
    seconds,
    id,
    top,
    left,
    color,
    project,
    projectLabel,
    service,
    serviceLabel,
  } = activity
  const [showSettings, setShowSettings] = useState(false)

  const [services, setServices] = useState([])

  useEffect(() => {
    const servicesRequest = fetchServices(project)
      .then(response => response.json())
      .then(data => {
        setServices(
          data.services.map(row => ({
            label: row[1],
            value: row[0],
          }))
        )
      })
  }, [project])

  const update = fields =>
    dispatch({
      type: "UPDATE_ACTIVITY",
      activity: id,
      fields,
    })

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

  const style = {backgroundColor: color || "#e3f2fd"}

  const settingsPanel = showSettings ? (
    <div className="activity-settings d-flex align-items-center justify-content-between">
      <input
        type="color"
        value={color || "#e3f2fd"}
        onChange={e => update({color: e.target.value})}
      />
      {/*
                  <button className="btn btn-secondary" type="button">
                    Duplicate
                  </button>
                  */}
      <button
        className="btn btn-danger"
        type="button"
        onClick={() => {
          dispatch({type: "REMOVE_ACTIVITY", activity: id})
        }}
      >
        Remove
      </button>
    </div>
  ) : null

  return (
    <Draggable
      handle=".js-drag-handle"
      defaultPosition={{
        x: clamp(
          left,
          0,
          500
        ) /* TODO use innerWidth / innerHeight of window */,
        y: clamp(top, 0, 500),
      }}
      onStop={(e, data) =>
        update({
          left: data.x,
          top: data.y,
        })
      }
    >
      <form className="activity card px-2 py-2" style={style}>
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
        <div className="activity-body" style={style}>
          {settingsPanel}
          <div className="form-group">
            <AsyncSelect
              className="select"
              classNamePrefix="select"
              loadOptions={async (inputValue, callback) => {
                const projects = await fetchProjects(inputValue)
                const data = await projects.json()
                callback(data.results)
              }}
              onChange={row => {
                update({project: row.value, projectLabel: row.label})
              }}
              placeholder={projectLabel}
            />
          </div>
          <div className="form-group">
            <Select
              className="select"
              classNamePrefix="select"
              options={services}
              onChange={row => {
                update({service: row.value, serviceLabel: row.label})
              }}
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
          <div className="activity-duration mb-2">
            {prettyDuration(mySeconds)}
          </div>
          <div className="d-flex justify-content-between">
            <button
              className="btn btn-success"
              type="button"
              onClick={e => {
                e.preventDefault()
                if (isActive) {
                  dispatch({
                    type: "STOP",
                    current: current,
                  })
                } else {
                  dispatch({
                    type: "START",
                    activity: id,
                    current: current,
                  })
                }
              }}
            >
              {isActive ? "Pause" : "Start"}
            </button>
            <button
              className="btn btn-primary"
              type="button"
              onClick={() => {
                const url = endpointUrl({
                  name: "createHours",
                  urlParams: [project],
                })
                const fd = new URLSearchParams()
                fd.append("project", project)
                fd.append("service", service)
                fd.append("description", description)
                fd.append("hours", Math.ceil(mySeconds / 360) / 10)
                fd.append("date", new Date().toISOString().replace(/T.*/, ""))

                const finalUrl = `${url}?${fd.toString()}`
                console.log(finalUrl)
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
              Send
            </button>
          </div>
        </div>
      </form>
    </Draggable>
  )
})
