import assert from "node:assert/strict"
import { test } from "node:test"

import { colorClass, position, prettyDuration } from "./utils.js"

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
