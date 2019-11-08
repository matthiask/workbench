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
  const hours = Math.floor(seconds / 3600)
  const displayHours = hours ? `${hours}:` : ""
  const displayMinutes = (Math.floor(seconds / 60) % 60)
    .toString()
    .padStart(hours ? 2 : 1, "0")
  const displaySeconds = (seconds % 60).toString().padStart(2, "0")
  return `${displayHours}${displayMinutes}:${displaySeconds}`
}

export function containsJSON(response) {
  const contentType = response.headers.get("content-type")
  return (contentType && contentType.includes("application/json"))
}

export function debounce(func, wait, immediate) {
  let timeout

  return function() {
    let context = this
    let args = arguments

    clearTimeout(timeout)

    timeout = setTimeout(function() {
      timeout = null

      if (!immediate) {
        func.apply(context, args)
      }
    }, wait)

    if (immediate && !timeout) {
      func.apply(context, args)
    }
  }
}
