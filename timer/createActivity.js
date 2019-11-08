import React, {useRef, useState} from "react"
import {connect} from "react-redux"

import {createActivity} from "./actions.js"

export const CreateActivity = connect()(({dispatch}) => {
  const [description, setDescription] = useState("")
  const descriptionField = useRef()
  return (
    <form
      className="form-inline create-activity"
      onSubmit={e => {
        e.preventDefault()
        createActivity(dispatch, {description})
        setDescription("")
      }}
    >
      <div className="input-group">
        <input
          type="text"
          className="form-control"
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="Was willst Du erreichen?"
          ref={descriptionField}
        />
        <div className="input-group-append">
          <button className="btn btn-primary" type="submit">
            Start!
          </button>
        </div>
      </div>
    </form>
  )
})
