import {endpointUrl} from "../endpoints.js"

const FETCH_DEFAULT_CONFIG = {
  credentials: "include",
}

// export function fetchServices(projectId) {
//   return (dispatch, _getState) => {
//     const url = endpointUrl({name: "services", urlParams: [projectId]})
//     fetch(url, FETCH_DEFAULT_CONFIG)
//     dispatch()
//   }
// }

export function fetchProjects(q = "") {
  return async (dispatch, _getState) => {
    const url = endpointUrl({name: "services", urlParams: [q]})
    try {
      const projects = await fetch(url, FETCH_DEFAULT_CONFIG)

      dispatch({
        type: "ADD_PROJECTS",
        projects,
      })
    } catch (err) {
      console.error(err)
    }
  }
}
