import React from "react"

import {createStore, applyMiddleware, compose} from "redux"
import reducer from "./reducers"
// import thunk from "redux-thunk"
import logger from "redux-logger"
import persistState from "redux-localstorage"

const VERSION = 1

export function configureStore(initialState = undefined) {
  let store = createStore(
    reducer,
    initialState,
    compose(
      persistState(null, {
        serialize: data => {
          return JSON.stringify({...data, _v: VERSION})
        },
        deserialize: blob => {
          let parsed = JSON.parse(blob)
          if (!parsed || !parsed._v || parsed._v !== VERSION) return {}
          // eslint-disable-next-line no-unused-vars
          const {_v, ...data} = parsed
          return data
        },
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
