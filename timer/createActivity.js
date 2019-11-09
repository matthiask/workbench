import React, {useState} from "react"
import {connect} from "react-redux"

import {createActivity} from "./actions.js"
import {gettext, OUTCOME} from "./i18n.js"

export const CreateActivity = connect()(({dispatch}) => {
  const [description, setDescription] = useState("")
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
          placeholder={OUTCOME}
          style={{minWidth: "15rem"}}
        />
        <div className="input-group-append">
          <button className="btn btn-primary" type="submit">
            {gettext("Start")}!
          </button>
        </div>
      </div>
    </form>
  )
})
