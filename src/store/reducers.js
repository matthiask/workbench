import {combineReducers} from "redux"

function activities(state = [], action) {
  switch (action.type) {
    case "ADD_ACTIVITY":
      return state.concat([action.activity])
    default:
      return state
  }
}

function projects(state = [], action) {
  switch (action.type) {
    case "ADD_PROJECTS":
      return action.projects
    default:
      return state
  }
}

const reducer = combineReducers({
  activities,
  projects,
})

export default reducer
