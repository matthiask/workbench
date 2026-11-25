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

// Position of an element relative to the area, in the area's CSS pixels
export function areaBox(area, el) {
  const areaRect = area.getBoundingClientRect()
  // Ratio of rendered to CSS pixels, in case the area is zoomed
  const k = areaRect.width / area.offsetWidth || 1
  const rect = el.getBoundingClientRect()
  return {
    left: (rect.left - areaRect.left) / k,
    top: (rect.top - areaRect.top) / k,
    right: (rect.right - areaRect.left) / k,
    bottom: (rect.bottom - areaRect.top) / k,
  }
}

// Where a new activity of `size` goes within `visible`: the first spot in
// reading order which doesn't touch the `occupied` rectangles, or the one
// overlapping them least if there's no room. Spots are on the grid of
// `step`, so the gap to others is at most one step.
export function freeSpot(visible, occupied, size, { step = 10, gap = 1 } = {}) {
  const up = (value) => step * Math.ceil(value / step)
  const range = (from, to) => {
    const values = []
    for (let v = up(from); v <= Math.max(to, up(from)); v += step) {
      values.push(v)
    }
    return values
  }
  const overlap = (left, top) =>
    occupied.reduce((sum, r) => {
      const w =
        Math.min(left + size.width, r.right + gap) -
        Math.max(left, r.left - gap)
      const h =
        Math.min(top + size.height, r.bottom + gap) - Math.max(top, r.top - gap)
      return w > 0 && h > 0 ? sum + w * h : sum
    }, 0)

  let best = null
  for (const top of range(visible.top, visible.bottom - size.height)) {
    for (const left of range(visible.left, visible.right - size.width)) {
      const value = overlap(left, top)
      if (value === 0) return { left, top }
      if (!best || value < best.value) best = { left, top, value }
    }
  }
  return { left: best.left, top: best.top }
}

// A free spot in the visible part of the timer for a new activity
export function newActivityPosition(size) {
  const area = document.querySelector(".activity-list")
  if (!area) {
    // Not rendered yet
    return {
      left: 10 * Math.floor((Math.random() * (window.innerWidth - 300)) / 10),
      top: 10 * Math.floor((Math.random() * (window.innerHeight - 300)) / 10),
    }
  }
  const areaRect = area.getBoundingClientRect()
  const k = areaRect.width / area.offsetWidth || 1
  const toArea = (r) => ({
    left: (r.left - areaRect.left) / k,
    top: (r.top - areaRect.top) / k,
    right: (r.right - areaRect.left) / k,
    bottom: (r.bottom - areaRect.top) / k,
  })
  const visible = toArea({
    left: 0,
    top: 0,
    right: document.documentElement.clientWidth,
    bottom: document.documentElement.clientHeight,
  })
  visible.left = Math.max(visible.left, 0)
  visible.top = Math.max(visible.top, 0)
  const occupied = [
    ...area.querySelectorAll("[data-activity]"),
    // Fixed elements on top of the activities
    ...document.querySelectorAll(
      ".wb-navbar, .create-activity, .total-seconds",
    ),
  ].map((el) => toArea(el.getBoundingClientRect()))
  return freeSpot(visible, occupied, size)
}

// Lays out activities in rows from `left` and `top`, wrapping before
// `right`, in the reading order of their current positions. Each starts on
// the first line of the grid of `step` after the previous one ends.
export function arrange(items, { left, top, right, gap = 1, step = 10 }) {
  const up = (value) => step * Math.ceil(value / step)
  const sorted = [...items].sort((a, b) => a.top - b.top || a.left - b.left)
  const positions = {}
  let x = up(left)
  let y = up(top)
  let rowHeight = 0
  for (const item of sorted) {
    if (x > up(left) && x + item.width > right) {
      x = up(left)
      y = up(y + rowHeight + gap)
      rowHeight = 0
    }
    positions[item.id] = { left: x, top: y }
    x = up(x + item.width + gap)
    rowHeight = Math.max(rowHeight, item.height)
  }
  return positions
}

// Scrolls the page while the pointer is near an edge of the window during a
// drag (at the top, below the sticky navbar), faster the closer it gets.
// `onScroll` gets the pointer position after each step, so that what's
// dragged keeps following the pointer. Returns a function which stops it.
export function startAutoScroll(onScroll, { edge = 50, speed = 30 } = {}) {
  let pointer = null
  const track = (e) => {
    pointer = { x: e.clientX, y: e.clientY }
  }
  const step = (position, start, end) => {
    if (position < start + edge)
      return -speed * Math.min(1, (start + edge - position) / edge)
    if (position > end - edge)
      return speed * Math.min(1, (position - end + edge) / edge)
    return 0
  }
  let frame
  const tick = () => {
    frame = requestAnimationFrame(tick)
    if (!pointer) return
    const root = document.documentElement
    const top =
      document.querySelector(".wb-navbar")?.getBoundingClientRect().bottom || 0
    const dx = Math.round(step(pointer.x, 0, root.clientWidth))
    const dy = Math.round(step(pointer.y, top, root.clientHeight))
    if (!dx && !dy) return
    const before = [window.scrollX, window.scrollY]
    // Instantly: Bootstrap makes scrolling smooth, which would restart its
    // animation on every step and barely move
    window.scrollBy({ left: dx, top: dy, behavior: "instant" })
    if (window.scrollX !== before[0] || window.scrollY !== before[1]) {
      onScroll(pointer.x, pointer.y)
    }
  }
  window.addEventListener("pointermove", track)
  frame = requestAnimationFrame(tick)
  return () => {
    cancelAnimationFrame(frame)
    window.removeEventListener("pointermove", track)
  }
}

// Activities can be dragged within the visible area or the area other
// activities already use, whichever is larger, but never further out.
// `nodes` are all activities moved together, `node` the one being dragged.
export function dragBounds(node, nodes) {
  const area = node.parentElement
  let right = area.offsetWidth
  let bottom = area.offsetHeight
  for (const el of area.querySelectorAll("[data-activity]")) {
    if (nodes.includes(el)) continue
    const other = areaBox(area, el)
    right = Math.max(right, other.right)
    bottom = Math.max(bottom, other.bottom)
  }
  const boxes = nodes.map((el) => areaBox(area, el))
  const group = {
    left: Math.min(...boxes.map((b) => b.left)),
    top: Math.min(...boxes.map((b) => b.top)),
    right: Math.max(...boxes.map((b) => b.right)),
    bottom: Math.max(...boxes.map((b) => b.bottom)),
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

  const self = areaBox(area, node)
  return {
    left: self.left - group.left,
    top: self.top - group.top,
    right: self.left + Math.max(right - group.right, 0),
    bottom: self.top + Math.max(bottom - group.bottom, 0),
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

// Relative luminance (WCAG) of a #rrggbb color
function luminance(color) {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = Number.parseInt(color.slice(i, i + 2), 16) / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

// Text on colored activities is dark (#1d2127), or white on dark colors
// where white contrasts more
const DARK_TEXT = luminance("#1d2127")

export function colorClass(color) {
  if (!hasColor(color)) return ""
  if (!/^#[0-9a-f]{6}$/i.test(color)) return "has-color"
  const l = luminance(color)
  return 1.05 / (l + 0.05) > (l + 0.05) / (DARK_TEXT + 0.05)
    ? "has-color has-dark-color"
    : "has-color"
}

export function colorStyle(color) {
  return hasColor(color) ? { backgroundColor: color } : {}
}
