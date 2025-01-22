import { compose, createStore } from "redux"
import persistState from "redux-localstorage"
import reducer from "./reducers"

const VERSION = 3

const serialize = (data) => {
  return JSON.stringify({ ...data, _v: VERSION })
}

const deserialize = (blob) => {
  const deserializeRaw = () => {
    const parsed = JSON.parse(blob)
    if (!parsed || !parsed._v) return {}
    const { _v, ...data } = parsed
    if (_v === VERSION) {
      return data
    }
    if (_v === 2) {
      return data
    }
    if (_v === 1) {
      return {
        ...data,
        activities: Object.fromEntries(
          data.activities.map((activity) => [activity.id, activity]),
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
        ([id]) => id && id !== "null" && id !== "undefined",
      ),
    ),
  }
}

export function configureStore() {
  let initialState
  try {
    initialState = JSON.parse(
      document.getElementById("timer-state").textContent,
    )
  } catch (_e) {
    /* intentionally empty */
  }
  const store = createStore(
    reducer,
    initialState,
    compose(
      persistState(null, {
        serialize,
        deserialize,
      }),
    ),
  )

  if (module.hot) {
    module.hot.accept(() => {
      const reducer = require("./reducers").default
      store.replaceReducer(reducer)
    })
  }

  return store
}
