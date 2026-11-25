export function createIdentifier() {
  return `${Date.now()}.${Math.floor(Math.random() * 10000)}`
}

export function timestamp() {
  return Date.now() / 1000
}

// Positions aren't limited to the window: activities arranged on a larger
// screen stay where they are and the page scrolls on a smaller one.
export function position(activity) {
  const snap = (value) => 10 * Math.floor(Math.max(value || 0, 0) / 10)
  return { x: snap(activity.left), y: snap(activity.top) }
}

// Activities can be dragged within the visible area or the area other
// activities already use, whichever is larger, but never further out.
export function dragBounds(node) {
  const area = node.parentElement
  const areaRect = area.getBoundingClientRect()
  // Ratio of rendered to CSS pixels, in case the area is zoomed
  const k = areaRect.width / area.offsetWidth || 1
  const box = (el) => {
    const rect = el.getBoundingClientRect()
    return {
      left: (rect.left - areaRect.left) / k,
      top: (rect.top - areaRect.top) / k,
      right: (rect.right - areaRect.left) / k,
      bottom: (rect.bottom - areaRect.top) / k,
    }
  }
  let right = area.offsetWidth
  let bottom = area.offsetHeight
  for (const el of area.children) {
    if (el === node) continue
    const other = box(el)
    right = Math.max(right, other.right)
    bottom = Math.max(bottom, other.bottom)
  }
  // Keep the area's size while dragging: if it shrank, the browser would
  // scroll and move the area under the pointer, and the activity with it.
  area.style.minWidth = `${area.scrollWidth}px`
  area.style.minHeight = `${area.scrollHeight}px`
  window.addEventListener(
    "pointerup",
    () => {
      area.style.minWidth = ""
      area.style.minHeight = ""
    },
    { once: true },
  )

  const self = box(node)
  return {
    left: 0,
    top: 0,
    right: Math.max(right - node.offsetWidth, self.left),
    bottom: Math.max(bottom - node.offsetHeight, self.top),
  }
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

// White was the default color, uncolored activities use the theme's surface
export function hasColor(color) {
  return Boolean(color) && color.toLowerCase() !== "#ffffff"
}

export function colorStyle(color) {
  return hasColor(color) ? { backgroundColor: color } : {}
}
