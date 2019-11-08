import "./index.scss"

import ReactDOM from "react-dom"
import React from "react"
import {Provider as ReduxProvider} from "react-redux"

import {configureStore} from "./store/store.js"

import {Activities} from "./activities.js"
import {CreateActivity} from "./createActivity.js"
import {endpointUrl} from "./endpoints.js"
import {initOneWindow} from "./oneWindow.js"
import {createActivity} from "./store/actions.js"
import {containsJSON} from "./utils.js"

const store = configureStore()

async function loadProjects(dispatch) {
  const response = await fetch(endpointUrl({name: "activeProjects"}), {
    credentials: "include",
  })
  if (containsJSON(response)) {
    const data = await response.json()
    dispatch({
      type: "PROJECTS",
      projects: data.projects,
    })
  }
}

export const App = () => {
  loadProjects(store.dispatch)
  return (
    <ReduxProvider store={store}>
      <nav className="navbar navbar-light bg-light">
        <span className="navbar-brand">Timer</span>
        <CreateActivity />
      </nav>
      <Activities />
    </ReduxProvider>
  )
}

document.addEventListener("DOMContentLoaded", () => {
  ReactDOM.render(<App />, document.getElementById("root"))
  initOneWindow()

  // window.jQuery(document).on("modalform", (e, xhrStatus, action) => {
  window.jQuery(document).on("modalform", () => {
    store.dispatch({
      type: "UPDATE_ACTIVITY",
      activity: store.getState().modalActivity,
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
