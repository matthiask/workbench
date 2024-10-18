export function createIdentifier() {
  return `${new Date().getTime()}.${Math.floor(Math.random() * 10000)}`
}

export function timestamp() {
  return new Date().getTime() / 1000
}

export function clamp(value, min, max) {
  return Math.max(Math.min(value || 0, max), min)
}

export function prettyDuration(secondsArgument) {
  const seconds = Math.ceil(secondsArgument) || 0
  return [
    Math.floor(seconds / 3600),
    Math.floor(seconds / 60) % 60,
    seconds % 60,
  ]
    .filter((part, idx) => idx || part)
    .map((part, idx) => (idx ? part.toString().padStart(2, "0") : part))
    .join(":")
}

export function containsJSON(response) {
  const contentType = response.headers.get("content-type")
  return contentType?.includes("application/json")
}
