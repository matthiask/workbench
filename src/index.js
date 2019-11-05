import "./scss/index.scss"

import ReactDOM from "react-dom"
import React from "react"
import {Provider as ReduxProvider} from "react-redux"

import {configureStore} from "./store/store.js"

import {Activity} from "./activity.js"

const store = configureStore()

export const App = () => {
  return (
    <ReduxProvider store={store}>
      <Activity />
    </ReduxProvider>
  )
}

ReactDOM.render(<App />, document.getElementById("root"))
