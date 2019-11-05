export function createIdentifier() {
  return `${new Date().getTime()}.${Math.floor(Math.random() * 10000)}`
}

export function timestamp() {
  return Math.floor(new Date().getTime() / 1000)
}

export function prettyDuration(secondsArgument) {
  const seconds = Math.floor(secondsArgument) || 0
  const hours = Math.floor(seconds / 3600)
  const displayHours = hours ? `${hours}h ` : ""
  const displayMinutes = Math.floor(seconds / 60) % 60
  const displaySeconds = (seconds % 60).toString().padStart(2, "0")
  return `${displayHours}${displayMinutes}:${displaySeconds}`
}

const snakeToCamel = string =>
  string.replace(/(_\w)/g, match => match[1].toUpperCase())

export function mapSnakeCaseToCamelCase(object) {
  const camelCaseObject = {}

  for (let key in object) {
    camelCaseObject[snakeToCamel(key)] = object[key]
  }

  return camelCaseObject
}

export const containsJSON = response => {
  const contentType = response.headers.get("content-type")

  if (contentType && contentType.includes("application/json")) {
    return true
  } else {
    return false
  }
}
