import React from "react"

import {createStore, applyMiddleware, compose} from "redux"
import reducer from "./reducers"
import thunk from "redux-thunk"
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
          data._v = VERSION
          return JSON.stringify(data)
        },
        deserialize: blob => {
          let parsed = JSON.parse(blob)
          if (!parsed._v || parsed._v !== VERSION) return {}
          // eslint-disable-next-line no-unused-vars
          const {_v, ...data} = parsed
          return data
        },
      }),
      applyMiddleware(thunk, logger)
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
