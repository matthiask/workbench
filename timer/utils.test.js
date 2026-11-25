import assert from "node:assert/strict"
import { test } from "node:test"

import { colorClass, freeSpot, position, prettyDuration } from "./utils.js"

test("positions snap to the grid and aren't limited to the window", () => {
  assert.deepEqual(position({ left: 1704, top: 2399 }), { x: 1700, y: 2390 })
  assert.deepEqual(position({ left: -30, top: undefined }), { x: 0, y: 0 })
})

test("dark colors get white text, light colors dark text", () => {
  assert.equal(colorClass(null), "")
  assert.equal(colorClass("#ffffff"), "")
  assert.equal(colorClass("#FFFFFF"), "")
  assert.equal(colorClass("#1a237e"), "has-color has-dark-color")
  assert.equal(colorClass("#8b0000"), "has-color has-dark-color")
  assert.equal(colorClass("#ffd54f"), "has-color")
  assert.equal(colorClass("#90caf9"), "has-color")
  // Unknown formats keep the dark text
  assert.equal(colorClass("red"), "has-color")
})

test("durations", () => {
  assert.equal(prettyDuration(0), "0:00")
  assert.equal(prettyDuration(59.2), "1:00")
  assert.equal(prettyDuration(3725), "1:02:05")
})

test("new activities go to the first free spot", () => {
  const visible = { left: 0, top: 0, right: 1000, bottom: 600 }
  const size = { width: 286, height: 250 }
  assert.deepEqual(freeSpot(visible, [], size), { left: 0, top: 0 })
  // Next to an activity in the top left corner, with a gap
  const first = { left: 20, top: 20, right: 306, bottom: 270 }
  assert.deepEqual(freeSpot(visible, [first], size), { left: 320, top: 0 })
  // Below the first row if it's full
  const row = [0, 310, 620].map((left) => ({
    left,
    top: 0,
    right: left + 286,
    bottom: 250,
  }))
  assert.deepEqual(freeSpot(visible, row, size), { left: 0, top: 260 })
})

test("without room, new activities overlap others least", () => {
  const visible = { left: 0, top: 0, right: 400, bottom: 300 }
  const size = { width: 286, height: 250 }
  const full = { left: 0, top: 0, right: 300, bottom: 300 }
  assert.deepEqual(freeSpot(visible, [full], size), { left: 110, top: 0 })
})

test("a visible area smaller than an activity still has a spot", () => {
  const visible = { left: 15, top: 5, right: 100, bottom: 100 }
  assert.deepEqual(freeSpot(visible, [], { width: 286, height: 250 }), {
    left: 20,
    top: 10,
  })
})
