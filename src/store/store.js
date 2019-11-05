import React from "react"

import {createStore, applyMiddleware} from "redux"
import reducer from "./reducers"
import thunk from "redux-thunk"
import logger from "redux-logger"

export function configureStore(initialState = undefined) {
  let store = createStore(reducer, initialState, applyMiddleware(thunk, logger))

  if (module.hot) {
    module.hot.accept(() => {
      let reducer = require("./reducers").default
      store.replaceReducer(reducer)
    })
  }

  // dispatch action to fetch initial data
  // store.dispatch(fetchFilter())

  return store
}
