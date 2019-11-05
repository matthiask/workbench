import React, {useState, useRef, useEffect} from "react"
import Draggable from "react-draggable"
import {connect} from "react-redux"

import {prettyDuration, containsJSON} from "./utils.js"
import {endpointUrl} from "./endpoints.js"

const fetchProjects = q => {
  const url = endpointUrl({name: "projects", urlParams: [q]})
  return fetch(url, {credentials: "include"})
}

export const Activity = connect()(
  ({description, seconds, id, top, left, dispatch}) => {
    const [showSettings, setShowSettings] = useState(false)
    const [color, setColor] = useState("#e3f2fd")
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

    const style = {backgroundColor: color}
    return (
      <Draggable
        handle=".js-drag-handle"
        onStop={(e, data) => {
          console.log(e, data)
        }}
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
                    value={color}
                    onChange={e => setColor(e.target.value)}
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
                <input
                  type="text"
                  className="form-control"
                  ref={projectInput}
                />
              </div>
              <div className="form-group">
                <label>Leistung</label>
                <input
                  type="text"
                  className="form-control"
                  ref={serviceInput}
                />
              </div>
              <div className="form-group">
                <label>Tätigkeit</label>
                <textarea
                  className="form-control"
                  rows="3"
                  value={description}
                />
              </div>
              <div className="activity-duration">{prettyDuration(seconds)}</div>
            </div>
            <div className="card-footer d-flex justify-content-between">
              <button className="btn btn-success">Pause</button>
              <button className="btn btn-primary">Send</button>
            </div>
          </div>
        </form>
      </Draggable>
    )
  }
)
