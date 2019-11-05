import "./scss/index.scss"

import ReactDOM from "react-dom"
import React from "react"
import {Provider as ReduxProvider} from "react-redux"

import {configureStore} from "./store/store.js"

import {Activities} from "./activities.js"
import {CreateActivity} from "./createActivity.js"

const store = configureStore()

export const App = () => {
  return (
    <ReduxProvider store={store}>
      <header className="timer-header">
        <h1>Timer</h1>
      </header>
      <Activities />
      <CreateActivity />
    </ReduxProvider>
  )
}

ReactDOM.render(<App />, document.getElementById("root"))
