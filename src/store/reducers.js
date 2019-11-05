import {combineReducers} from "redux"

function timers(state = [], action) {
  switch (action.type) {
    case "ADD_TIMER":
      return state.concat([action.timer])
    default:
      return state
  }
}

const reducer = combineReducers({
  timers,
})

export default reducer
