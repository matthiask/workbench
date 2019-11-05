import React, {useState, useRef, useEffect} from "react"
import Draggable from "react-draggable"
import {connect} from "react-redux"

import {clamp, prettyDuration, timestamp, containsJSON} from "./utils.js"
import {endpointUrl} from "./endpoints.js"

const fetchProjects = q => {
  const url = endpointUrl({name: "projects", urlParams: [q]})
  return fetch(url, {credentials: "include"})
}

export const Activity = connect((state, ownProps) => ({
  ...ownProps,
  current: state.current,
}))(({description, seconds, id, top, left, color, current, dispatch}) => {
  const [showSettings, setShowSettings] = useState(false)
  const [_project, setProject] = useState(null)
  const projectInput = useRef(null)
  const serviceInput = useRef(null)

  useEffect(() => {
    if (projectInput) {
      const $projectInput = window.$(projectInput.current)
      $projectInput.autocomplete({
        minLength: 2,
        source: async function(request, response) {
          try {
            const res = await fetchProjects(request.term)
            if (res.ok && containsJSON(res)) {
              const data = await res.json()
              response(data.results)
            } else {
              console.error(res.status, res.statusText)
            }
          } catch (err) {
            console.error(err)
          }
        },
        focus: function(event, ui) {
          $projectInput.val(ui.item.label)
          return false
        },
        select: function(event, ui) {
          $projectInput.val(ui.item.label)
          setProject(ui.item.value)
          // input.val(ui.item.value).trigger("change")
          return false
        },
      })
    }

    if (serviceInput) {
      window.$(serviceInput.current).autocomplete()
    }

    return () => {
      window.$(projectInput.current).autocomplete("destroy")
      window.$(serviceInput.current).autocomplete("destroy")
    }
  }, [projectInput, serviceInput])

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
      <form className="activity">
        <div className="card">
          <div className="card-header d-flex w-100 align-items-center justify-content-between js-drag-handle">
            <h5>Aktivität</h5>
            <button
              className="btn btn-outline-secondary"
              type="button"
              onClick={() => setShowSettings(!showSettings)}
            >
              &#x2056;
            </button>
          </div>
          <div className="card-body" style={style}>
            {showSettings ? (
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
            ) : null}
            <div className="form-group">
              <label>Projekt</label>
              <input type="text" className="form-control" ref={projectInput} />
            </div>
            <div className="form-group">
              <label>Leistung</label>
              <input type="text" className="form-control" ref={serviceInput} />
            </div>
            <div className="form-group">
              <label>Tätigkeit</label>
              <textarea
                className="form-control"
                rows="3"
                value={description}
                onChange={e => update({description: e.target.value})}
                placeholder="Was willst Du erreichen?"
              />
            </div>
            <div className="activity-duration">{prettyDuration(mySeconds)}</div>
          </div>
          <div className="card-footer d-flex justify-content-between">
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
            <button className="btn btn-primary" type="button">
              Send
            </button>
          </div>
        </div>
      </form>
    </Draggable>
  )
})
