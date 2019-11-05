import React, {useState} from "react"
import Draggable from "react-draggable"

import {prettyDuration} from "./utils.js"

export const Activity = ({description, seconds, top, left}) => {
  const [showSettings, setShowSettings] = useState(false)
  const [color, setColor] = useState("#e3f2fd")

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
              className="btn btn-primary"
              type="button"
              onClick={() => setShowSettings(!showSettings)}
            >
              &#x2056;
            </button>
          </div>
          <div className="card-body" style={style}>
            {showSettings ? (
              <div className="activity-settings">
                <input
                  type="color"
                  value={color}
                  onChange={e => setColor(e.target.value)}
                />
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
              <textarea className="form-control" rows="3" value={description} />
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
