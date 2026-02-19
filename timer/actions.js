import { gettext } from "./i18n.js"
import { containsJSON, createIdentifier } from "./utils.js"

const BASE_URL = document.getElementById("projects-base-url").dataset.url
const ACTIVE_PROJECTS = () => `${BASE_URL}projects/`
const PROJECT_SEARCH = (q) => `${BASE_URL}autocomplete/?only_open=1&q=${q}`
const SERVICES = (id) => `${BASE_URL}${id}/services/`
const CREATE_HOURS = (id) => `${BASE_URL}${id}/createhours/`
const endpoint = (fn, ...args) => fn(...args)

export function createBreak(dispatch) {
  dispatch({
    type: "ADD_ACTIVITY",
    activity: {
      type: "break",
      description: "",
      startedAt: null,
      id: createIdentifier(),
      left: 10 * Math.floor((Math.random() * (window.innerWidth - 300)) / 10),
      top: 10 * Math.floor((Math.random() * (window.innerHeight - 300)) / 10),
      color: "#ffffff",
    },
  })
}

const BREAK_URL = "/logbook/breaks/create/"
const pad = (n) => String(n).padStart(2, "0")
const formatDate = (d) =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const formatTime = (d) => `${pad(d.getHours())}:${pad(d.getMinutes())}`

export async function saveBreak(dispatch, activity, { reload = true } = {}) {
  const startedAt = new Date(activity.startedAt * 1000)
  const endedAt = new Date()

  const body = new FormData()
  body.append("modal-day", formatDate(endedAt))
  body.append("modal-starts_at", formatTime(startedAt))
  body.append("modal-ends_at", formatTime(endedAt))
  if (activity.description)
    body.append("modal-description", activity.description)

  const headers = new Headers()
  headers.append("X-Requested-With", "XMLHttpRequest")
  headers.append("X-CSRFToken", document.cookie.match(/\bcsrftoken=(.+?)\b/)[1])

  const response = await fetch(BREAK_URL, {
    credentials: "include",
    method: "POST",
    body,
    headers,
  })
  if (response.status === 201) {
    dispatch({
      type: "UPDATE_ACTIVITY",
      id: activity.id,
      fields: { startedAt: null, description: "" },
    })
    if (reload) window.location.reload()
  } else {
    window.initModal(await response.text())
  }
}

export function createActivity(dispatch, fields = {}) {
  dispatch({
    type: "ADD_ACTIVITY",
    activity: {
      description: "",
      seconds: 0,
      id: createIdentifier(),
      left: 10 * Math.floor((Math.random() * (window.innerWidth - 300)) / 10),
      top: 10 * Math.floor((Math.random() * (window.innerHeight - 300)) / 10),
      color: "#ffffff",
      ...fields,
    },
  })
}

export async function fetchProjects(q) {
  const response = await fetch(endpoint(PROJECT_SEARCH, q), {
    credentials: "include",
  })
  if (containsJSON(response)) {
    const data = await response.json()
    return data.results
  }
  return []
}

export async function fetchServices(project) {
  const response = await fetch(endpoint(SERVICES, project), {
    credentials: "include",
  })
  if (containsJSON(response)) {
    const data = await response.json()
    return data.services
  }
  return []
}

export async function loadProjects(dispatch) {
  const response = await fetch(endpoint(ACTIVE_PROJECTS), {
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

export async function openForm(dispatch, { activity, current }) {
  if (current && current.id === activity.id) dispatch({ type: "STOP", current })
  dispatch({ type: "MODAL_ACTIVITY", id: activity.id })

  const url = endpoint(CREATE_HOURS, activity.project.value)
  const params = new URLSearchParams()
  if (activity.service) {
    params.append("service", activity.service.value)
  }
  if (activity.seconds) {
    params.append("hours", Math.ceil(activity.seconds / 360) / 10)
  }
  params.append("description", activity.description)

  const finalUrl = `${url}?${params.toString()}`
  console.log(finalUrl)
  window.openModalFromUrl(finalUrl)
  return
}

export async function sendLogbook(dispatch, { activity, current }) {
  const url = endpoint(CREATE_HOURS, activity.project.value)

  const body = new FormData()
  if (activity.service) body.append("modal-service", activity.service.value)
  body.append("modal-description", activity.description)
  body.append("modal-hours", Math.ceil(activity.seconds / 360) / 10)
  body.append(
    "modal-rendered_by",
    document.getElementById("current-user").dataset.currentUser,
  )
  body.append("modal-rendered_on", new Date().toISOString().replace(/T.*/, ""))

  const headers = new Headers()
  headers.append("X-Requested-With", "XMLHttpRequest")
  headers.append("X-CSRFToken", document.cookie.match(/\bcsrftoken=(.+?)\b/)[1])

  const response = await fetch(url, {
    credentials: "include",
    method: "POST",
    body,
    headers,
  })
  if (response.status === 200) {
    window.initModal(await response.text())
  } else if (response.status === 201) {
    if (current && current.id === activity.id)
      dispatch({ type: "STOP", current })
    dispatch({
      type: "UPDATE_ACTIVITY",
      id: activity.id,
      fields: { description: "", seconds: 0 },
    })
    window.location.reload()
  } else {
    alert(gettext("Unable to submit the logbook entry"))
  }
}

const formatForPrompt = (s) => {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  const pad = (n) => String(n).padStart(2, "0")
  return `${h}:${pad(m)}:${pad(sec)}`
}

const parseTimeInput = (input) => {
  const parts = input.trim().split(":")
  if (parts.length === 3) {
    const [h, m, s] = parts.map(Number)
    if ([h, m, s].some(Number.isNaN)) return Number.NaN
    return h * 3600 + m * 60 + s
  }
  if (parts.length === 2) {
    // m:s — one colon is NOT interpreted as h:m
    const [m, s] = parts.map(Number)
    if ([m, s].some(Number.isNaN)) return Number.NaN
    return m * 60 + s
  }
  return Number.parseInt(input, 10)
}

export function overwriteSeconds(dispatch, { activity, current }) {
  const input = prompt(
    gettext("Overwrite time (h:m:s or m:s or seconds)"),
    formatForPrompt(Math.ceil(activity.seconds)),
  )
  if (input === null) return
  const seconds = parseTimeInput(input)
  if (!Number.isNaN(seconds)) {
    dispatch({
      type: "UPDATE_ACTIVITY",
      id: activity.id,
      fields: { seconds },
    })
    if (current && current.id === activity.id) {
      dispatch({ type: "START", id: activity.id })
    }
  }
}
