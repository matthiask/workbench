import "./index.scss"

import ReactDOM from "react-dom"
import React from "react"
import {Provider as ReduxProvider} from "react-redux"

import {configureStore} from "./store/store.js"

import {Activities} from "./activities.js"
import {CreateActivity} from "./createActivity.js"
import {endpointUrl} from "./endpoints.js"
import {initOneWindow} from "./oneWindow.js"
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

ReactDOM.render(<App />, document.getElementById("root"))
initOneWindow()
