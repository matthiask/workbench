import React from "react"

import {createStore, applyMiddleware, compose} from "redux"
import reducer from "./reducers"
// import thunk from "redux-thunk"
import logger from "redux-logger"
import persistState from "redux-localstorage"

const VERSION = 2

const serialize = data => {
  return JSON.stringify({...data, _v: VERSION})
}

const deserialize = blob => {
  let parsed = JSON.parse(blob)
  if (!parsed || !parsed._v) return {}
  const {_v, ...data} = parsed
  if (_v == VERSION) {
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

export function configureStore(initialState = undefined) {
  let store = createStore(
    reducer,
    initialState,
    compose(
      persistState(null, {
        serialize,
        deserialize,
      }),
      applyMiddleware(
        // thunk,
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
