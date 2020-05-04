import React from "react"

import {createStore, applyMiddleware, compose} from "redux"
import reducer from "./reducers"
import thunk from "redux-thunk"
import logger from "redux-logger"
import persistState from "redux-localstorage"

const VERSION = 3

const initialTitle = document.title
const notifier = (store) => (next) => (action) => {
  const state = next(action)
  const {current} = store.getState()
  document.title = `${current ? "▶ " : ""}${initialTitle}`
  return state
}

const serialize = (data) => {
  return JSON.stringify({...data, _v: VERSION})
}

const deserialize = (blob) => {
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
          data.activities.map((activity) => [activity.id, activity])
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
      applyMiddleware(
        notifier,
        // remotePersister,
        thunk,
        logger
      )
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
