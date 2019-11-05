import React from "react"

export const Activity = _props => {
  return (
    <form>
      <div className="card">
        <div className="card-header"></div>
        <div className="card-body">
          <label>Projekt</label>
          <input type="text" />
          <label>Leistung</label>
          <input type="text" />
          <label>Tätigkeit</label>
          <input type="text" />
          <span>0:13:29</span>
        </div>
        <div className="card-footer">
          <button className="btn">Pause</button>
          <button className="btn">Send</button>
        </div>
      </div>
    </form>
  )
}
