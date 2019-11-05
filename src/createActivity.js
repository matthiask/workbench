import React, {useState} from "react"
import {connect} from "react-redux"

import {createIdentifier} from "./utils.js"

export const CreateActivity = connect()(({dispatch}) => {
  const [description, setDescription] = useState("")
  return (
    <form className="create-activity">
      <div className="card">
        <div className="card-body">
          <div className="form-group">
            <label>Tätigkeit</label>
            <input
              type="text"
              className="form-control"
              value={description}
              onChange={e => setDescription(e.target.value)}
            />
          </div>
          <button
            className="btn btn-primary"
            onClick={e => {
              e.preventDefault()
              dispatch({
                type: "ADD_ACTIVITY",
                activity: {description, seconds: 0, id: createIdentifier()},
              })
            }}
          >
            Create
          </button>
        </div>
      </div>
    </form>
  )
})
