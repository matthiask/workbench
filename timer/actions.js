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

export async function fetchProjects(q) {
  const url = endpointUrl({name: "projects", urlParams: [q]})
  const response = await fetch(url, {credentials: "include"})
  if (containsJSON(response)) {
    const data = await response.json()
    return data.results
  }
  return []
}

export async function fetchServices(project) {
  const url = endpointUrl({name: "services", urlParams: [project]})
  const response = await fetch(url, {credentials: "include"})
  if (containsJSON(response)) {
    const data = await response.json()
    return data.services.map(row => ({label: row[1], value: row[0]}))
  }
  return []
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

export function openLogbookForm(dispatch, {activity, current, seconds}) {
  const url = endpointUrl({
    name: "createHours",
    urlParams: [activity.project.value],
  })
  const fd = new URLSearchParams()
  if (activity.service) fd.append("service", activity.service.value)
  fd.append("description", activity.description)
  fd.append("hours", Math.ceil(seconds / 360) / 10)
  fd.append("date", new Date().toISOString().replace(/T.*/, ""))

  const finalUrl = `${url}?${fd.toString()}`
  console.log(finalUrl)
  dispatch({type: "STOP", current})
  dispatch({type: "MODAL_ACTIVITY", id: activity.id})
  window.openModalFromUrl(finalUrl)
}
