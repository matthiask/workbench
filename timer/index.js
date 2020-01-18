import "./index.scss"

import ReactDOM from "react-dom"
import React from "react"
import {Provider} from "react-redux"

import {createActivity, loadProjects} from "./actions.js"
import {initOneWindow} from "./oneWindow.js"
import {configureStore} from "./store.js"
import {Timer} from "./timer.js"

const storeInstance = configureStore()

document.addEventListener("DOMContentLoaded", () => {
  addModalActivityListener(storeInstance)
  initOneWindow()
  loadProjects(storeInstance.dispatch)
  migrateOldData(storeInstance.dispatch)

  const el = document.querySelector('div[role="main"]')
  ReactDOM.render(
    <Provider store={storeInstance}>
      <Timer />
    </Provider>,
    el
  )
})

function addModalActivityListener(store) {
  window.jQuery(document).on("modalform", () => {
    const {modalActivity} = store.getState()
    if (modalActivity) {
      store.dispatch({
        type: "UPDATE_ACTIVITY",
        id: modalActivity,
        fields: {description: "", seconds: 0},
      })
    }
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

import ReconnectingWebsocket from "reconnecting-websocket"
const timerData = JSON.parse(document.querySelector("#timer-data").textContent)

;(function() {
  const ws = new ReconnectingWebsocket(`ws://127.0.0.1:8080/${timerData.key}`)

  ws.addEventListener("open", arg => console.log("open", arg))
  ws.addEventListener("close", arg => console.log("close", arg))
  ws.addEventListener("message", arg => console.log("message", arg))

  setInterval(() => ws.send(`Hello from Browser ${navigator.userAgent}`), 5000)

  window.ws = ws
})()
