import { combineReducers } from "redux"

import { position, timestamp } from "./utils.js"

function activities(state, action) {
  if (typeof state === "undefined") {
    state = {}
  }
  switch (action.type) {
    case "ADD_ACTIVITY":
      return { ...state, [action.activity.id]: action.activity }
    case "REMOVE_ACTIVITY":
      return Object.fromEntries(
        Object.entries(state).filter(([id]) => id !== action.id),
      )
    case "UPDATE_ACTIVITY":
      return {
        ...state,
        [action.id]: {
          ...state[action.id],
          ...action.fields,
        },
      }
    case "MOVE_ACTIVITIES":
      return Object.fromEntries(
        Object.entries(state).map(([id, activity]) => {
          if (!action.ids.includes(id)) return [id, activity]
          const { x, y } = position(activity)
          return [id, { ...activity, left: x + action.dx, top: y + action.dy }]
        }),
      )
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

function current(state, action) {
  if (typeof state === "undefined") {
    state = null
  }
  switch (action.type) {
    case "START":
      return {
        id: action.id,
        startedAt: timestamp(),
      }
    case "STOP":
      return null
    case "REMOVE_ACTIVITY":
      return state && state.id === action.id ? null : state
    default:
      return state
  }
}

function modalActivity(state, action) {
  if (typeof state === "undefined") {
    state = null
  }
  switch (action.type) {
    case "MODAL_ACTIVITY":
      return action.id
    case "UPDATE_ACTIVITY":
      return null
    default:
      return state
  }
}

function projects(state, action) {
  if (typeof state === "undefined") {
    state = []
  }
  switch (action.type) {
    case "PROJECTS":
      return action.projects
    default:
      return state
  }
}

// Size of the activities, chosen per browser (e.g. smaller on a laptop)
export const ZOOM_LEVELS = [0.6, 0.7, 0.8, 0.9, 1]

function zoom(state, action) {
  if (typeof state === "undefined") {
    state = 1
  }
  switch (action.type) {
    case "ZOOM":
      return ZOOM_LEVELS.includes(action.zoom) ? action.zoom : state
    default:
      return state
  }
}

const reducer = combineReducers({
  activities,
  current,
  modalActivity,
  projects,
  zoom,
})

export default reducer
