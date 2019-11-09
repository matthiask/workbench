import "./index.scss"

import ReactDOM from "react-dom"
import React from "react"
import {Provider} from "react-redux"

import {createActivity, loadProjects} from "./actions.js"
import {initOneWindow} from "./oneWindow.js"
import {configureStore} from "./store.js"
import {Timer} from "./timer.js"

const store = configureStore()

document.addEventListener("DOMContentLoaded", () => {
  addModalActivityListener()
  initOneWindow()
  loadProjects(store.dispatch)
  migrateOldData(store.dispatch)
  ReactDOM.render(
    <Provider store={store}>
      <Timer />
    </Provider>,
    document.getElementById("root")
  )
})

function addModalActivityListener(store) {
  window.jQuery(document).on("modalform", () => {
    store.dispatch({
      type: "UPDATE_ACTIVITY",
      id: store.getState().modalActivity,
      fields: {description: "", seconds: 0},
    })
  })
}

function migrateOldData(dispatch) {
  try {
    const data = JSON.parse(localStorage.getItem("workbench-timer"))
    console.log(data)

    data.projects.forEach(project => {
      createActivity(dispatch, {
        project: {label: project.title, value: project.id},
        seconds: data.seconds[project.id] || 0,
      })
    })

    localStorage.removeItem("workbench-timer")
  } catch (e) {
    /* Do nothing */
  }
}
