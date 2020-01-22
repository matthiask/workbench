import React from "react"

import {createStore, applyMiddleware, compose} from "redux"
import reducer from "./reducers"
import thunk from "redux-thunk"
import logger from "redux-logger"
import persistState from "redux-localstorage"
import debounce from "lodash.debounce"

const VERSION = 3

const _debouncedSave = debounce(function(dispatch, state) {
  const headers = new Headers()
  headers.append("X-Requested-With", "XMLHttpRequest")
  headers.append("X-CSRFToken", document.cookie.match(/\bcsrftoken=(.+?)\b/)[1])

  const body = new FormData()
  // eslint-disable-next-line no-unused-vars
  const {projects, modalActivity, ...serverState} = state
  body.append("state", JSON.stringify(serverState))

  fetch(".", {
    credentials: "include",
    method: "POST",
    body,
    headers,
  })
    .then(response => response.json())
    .then(data => {
      window.console.log(data)
    })
    .catch(err => {
      window.console.error(err)
    })
}, 2500)

const remotePersister = store => next => action => {
  const state = next(action)
  _debouncedSave(store.dispatch, store.getState())
  return state
}

const serialize = data => {
  return JSON.stringify({...data, _v: VERSION})
}

const deserialize = blob => {
  const deserializeRaw = () => {
    let parsed = JSON.parse(blob)
    if (!parsed || !parsed._v) return {}
    const {_v, ...data} = parsed
    if (_v == VERSION) {
      return data
    } else if (_v == 2) {
      return data
    } else if (_v == 1) {
      return {
        ...data,
        activities: Object.fromEntries(
          data.activities.map(activity => [activity.id, activity])
        ),
      }
    }
    return {}
  }

  const data = deserializeRaw()
  return {
    ...data,
    activities: Object.fromEntries(
      Object.entries(data.activities).filter(
        ([id]) => id && id != "null" && id != "undefined"
      )
    ),
  }
}

const merge = (initial, persisted) => {
  initial = initial || {}
  persisted = persisted || {}
  return (initial.version || 0) > (persisted.version || 0) ? initial : persisted
}

export function configureStore() {
  let initialState
  try {
    initialState = JSON.parse(
      document.getElementById("timer-state").textContent
    )
  } catch (e) {
    /* intentionally empty */
  }
  let store = createStore(
    reducer,
    initialState,
    compose(
      persistState(null, {
        serialize,
        deserialize,
        merge,
      }),
      applyMiddleware(remotePersister, thunk, logger)
    )
  )

  if (module.hot) {
    module.hot.accept(() => {
      let reducer = require("./reducers").default
      store.replaceReducer(reducer)
    })
  }

  return store
}
