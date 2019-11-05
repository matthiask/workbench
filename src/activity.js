import React from "react"

export const Activity = _props => {
  return (
    <form>
      <div className="card">
        <div className="card-header"></div>
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
