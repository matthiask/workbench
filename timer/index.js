import "./index.scss"

import { createRoot } from "react-dom/client"
import { Provider } from "react-redux"

import { createActivity, loadProjects } from "./actions.js"
import { initOneWindow } from "./oneWindow.js"
import { configureStore } from "./store.js"
import { Timer } from "./timer.js"

const storeInstance = configureStore()

document.addEventListener("DOMContentLoaded", () => {
  addModalActivityListener(storeInstance)
  initOneWindow()
  loadProjects(storeInstance.dispatch)
  migrateOldData(storeInstance.dispatch)

  const el = document.querySelector('div[role="main"]')
  const root = createRoot(el)
  root.render(
    <Provider store={storeInstance}>
      <Timer />
    </Provider>,
  )
})

function addModalActivityListener(store) {
  // Forget the activity when its modal is closed without saving, otherwise
  // the next successful modal form submission (for something else entirely)
  // would reset the activity without its time ever having been logged.
  document.addEventListener("hide.bs.modal", () => {
    if (store.getState().modalActivity) {
      store.dispatch({ type: "MODAL_ACTIVITY", id: null })
    }
  })

  window.jQuery(document).on("modalform", () => {
    const { activities, modalActivity } = store.getState()
    if (modalActivity) {
      store.dispatch({
        type: "UPDATE_ACTIVITY",
        id: modalActivity,
        fields:
          activities[modalActivity]?.type === "break"
            ? { description: "", startedAt: null }
            : { description: "", seconds: 0 },
      })
    }
  })
}

function migrateOldData(dispatch) {
  try {
    const data = JSON.parse(localStorage.getItem("workbench-timer"))
    console.log(data)

    data.projects.forEach((project) => {
      createActivity(dispatch, {
        project: { label: project.title, value: project.id },
        seconds: data.seconds[project.id] || 0,
      })
    })

    localStorage.removeItem("workbench-timer")
  } catch (_e) {
    /* Do nothing */
  }
}
