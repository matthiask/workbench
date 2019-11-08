import {endpointUrl} from "./endpoints.js"
import {containsJSON, createIdentifier} from "./utils.js"

export function createActivity(dispatch, fields = {}) {
  dispatch({
    type: "ADD_ACTIVITY",
    activity: {
      description: "",
      seconds: 0,
      id: createIdentifier(),
      left: Math.floor(Math.random() * (window.innerWidth - 300)),
      top: Math.floor(Math.random() * (window.innerHeight - 300)),
      ...fields,
    },
  })
}

export async function loadProjects(dispatch) {
  const response = await fetch(endpointUrl({name: "activeProjects"}), {
    credentials: "include",
  })
  if (containsJSON(response)) {
    const data = await response.json()
    dispatch({
      type: "PROJECTS",
      projects: data.projects,
    })
  }
}
