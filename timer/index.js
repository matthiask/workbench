import "./index.scss"

import ReactDOM from "react-dom"
import React from "react"

import {createActivity, loadProjects} from "./actions.js"
import {initOneWindow} from "./oneWindow.js"
import {configureStore} from "./store.js"
import {Timer} from "./timer.js"

const store = configureStore()

document.addEventListener("DOMContentLoaded", () => {
  ReactDOM.render(<Timer store={store} />, document.getElementById("root"))
  initOneWindow()
  loadProjects(store.dispatch)

  // window.jQuery(document).on("modalform", (e, xhrStatus, action) => {
  window.jQuery(document).on("modalform", () => {
    store.dispatch({
      type: "UPDATE_ACTIVITY",
      id: store.getState().modalActivity,
      fields: {seconds: 0},
    })
  })

  // Migrate old data
  try {
    const data = JSON.parse(localStorage.getItem("workbench-timer"))
    console.log(data)

    data.projects.forEach(project => {
      createActivity(store.dispatch, {
        project: {label: project.title, value: project.id},
        seconds: data.seconds[project.id] || 0,
      })
    })

    localStorage.removeItem("workbench-timer")
  } catch (e) {
    /* Do nothing */
  }
})
