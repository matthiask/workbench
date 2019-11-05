import "./scss/index.scss"

import ReactDOM from "react-dom"
import React from "react"

import {Activity} from "./activity.js"

const HelloWorld = () => {
  return (
    <div>
      Hello world
      <Activity />
    </div>
  )
}

ReactDOM.render(<HelloWorld />, document.getElementById("root"))
