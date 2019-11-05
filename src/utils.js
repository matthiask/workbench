export function timestamp() {
  return Math.floor(new Date().getTime() / 1000)
}

export function prettyDuration(seconds) {
  const hours = Math.floor(seconds / 3600)
  const displayHours = hours ? `${hours}h ` : ""
  const displayMinutes = Math.floor(seconds / 60) % 60
  const displaySeconds = (seconds % 60).toString().padStart(2, "0")
  return `${displayHours}${displayMinutes}:${displaySeconds}`
}
