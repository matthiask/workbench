import {createIdentifier} from "../utils.js"

export function createActivity(dispatch, fields = {}) {
  dispatch({
    type: "ADD_ACTIVITY",
    activity: {
      seconds: 0,
      id: createIdentifier(),
      left: Math.floor(Math.random() * (window.innerWidth - 300)),
      top: Math.floor(Math.random() * (window.innerHeight - 300)),
      ...fields,
    },
  })
}
