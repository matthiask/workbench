import {combineReducers} from "redux"

import {timestamp} from "./utils.js"

function activities(state = {}, action) {
  switch (action.type) {
    case "ADD_ACTIVITY":
      return {...state, [action.activity.id]: action.activity}
    case "REMOVE_ACTIVITY":
      return Object.fromEntries(
        Object.entries(state).filter(([id]) => id != action.id)
      )
    case "UPDATE_ACTIVITY":
      return {
        ...state,
        [action.id]: {
          ...state[action.id],
          ...action.fields,
        },
      }
    case "START":
    case "STOP": {
      if (!action.current || !state[action.current.id]) return state
      const activity = state[action.current.id]
      return {
        ...state,
        [activity.id]: {
          ...activity,
          seconds: activity.seconds + (timestamp() - action.current.startedAt),
        },
      }
    }
    default:
      return state
  }
}

function current(state = null, action) {
  switch (action.type) {
    case "START":
      return {
        id: action.id,
        startedAt: timestamp(),
      }
    case "STOP":
      return null
    case "REMOVE_ACTIVITY":
      return state && state.id == action.id ? null : state
    default:
      return state
  }
}

function modalActivity(state = null, action) {
  switch (action.type) {
    case "MODAL_ACTIVITY":
      return action.id
    case "UPDATE_ACTIVITY":
      return null
    default:
      return state
  }
}

function projects(state = [], action) {
  switch (action.type) {
    case "PROJECTS":
      return action.projects
    default:
      return state
  }
}

function version(state = 0, action) {
  if (action.type.indexOf("@@") == 0) return state
  switch (action.type) {
    case "PROJECTS":
    case "MODAL_ACTIVITY":
      return state
    default:
      console.log("Incrementing version because of", action)
      return state + 1
  }
}

const reducer = combineReducers({
  activities,
  current,
  modalActivity,
  projects,
  version,
})

export default reducer
