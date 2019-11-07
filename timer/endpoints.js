const API = {
  host: "/",
  endpoints: {
    activeProjects: () => "projects/projects/",
    projects: q => `projects/autocomplete/?q=${q}&only_open=1`,
    services: id => `projects/${id}/services/`,
    createHours: id => `projects/${id}/createhours/`,
  },
}

export function endpointUrl({name, urlParams = []}) {
  if (!(name in API.endpoints)) return undefined
  return [API.host, API.endpoints[name](...urlParams)].join("")
}
