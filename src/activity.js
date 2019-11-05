import React, {useState} from "react"
import Draggable from "react-draggable"
import {connect} from "react-redux"

import {clamp, prettyDuration} from "./utils.js"

export const Activity = connect()(
  ({description, seconds, id, top, left, dispatch}) => {
    const [showSettings, setShowSettings] = useState(false)
    const [color, setColor] = useState("#e3f2fd")

    const style = {backgroundColor: color}
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
        onStop={(e, data) => {
          dispatch({
            type: "UPDATE_ACTIVITY",
            activity: id,
            fields: {
              left: data.x,
              top: data.y,
            },
          })
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
                <input type="text" className="form-control" />
              </div>
              <div className="form-group">
                <label>Leistung</label>
                <input type="text" className="form-control" />
              </div>
              <div className="form-group">
                <label>Tätigkeit</label>
                <textarea
                  className="form-control"
                  rows="3"
                  value={description}
                  onChange={e =>
                    dispatch({
                      type: "UPDATE_ACTIVITY",
                      activity: id,
                      fields: {description: e.target.value},
                    })
                  }
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
