import React from "react"
import Draggable from "react-draggable"

import {prettyDuration} from "./utils.js"

export const Activity = _props => {
  const style = {
    left: `${Math.floor(Math.random() * 500)}px`,
    top: `${Math.floor(Math.random() * 100)}px`,
  }
  return (
    <Draggable>
      <form className="activity" style={style}>
        <div className="card">
          <div className="card-header d-flex w-100 align-items-center justify-content-between">
            <h5>Aktivität</h5>
            <button className="btn btn-primary">&#x2056;</button>
          </div>
          <div className="card-body">
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
              <textarea className="form-control" rows="3" />
            </div>
            <span>{prettyDuration(Math.floor(Math.random() * 10800))}</span>
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
