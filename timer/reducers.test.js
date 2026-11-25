import assert from "node:assert/strict"
import { test } from "node:test"

import reducer from "./reducers.js"

const state = (activities, extra = {}) =>
  reducer(
    {
      activities: Object.fromEntries(activities.map((a) => [a.id, a])),
      ...extra,
    },
    { type: "INIT" },
  )

test("moving activities moves only those listed, from their grid position", () => {
  const before = state([
    { id: "a", left: 23, top: 41 },
    { id: "b", left: 300, top: 40 },
    { id: "c", left: 600, top: 40 },
  ])
  const after = reducer(before, {
    type: "MOVE_ACTIVITIES",
    ids: ["a", "b", "removed"],
    dx: 100,
    dy: -20,
  })
  assert.deepEqual(after.activities, {
    a: { id: "a", left: 120, top: 20 },
    b: { id: "b", left: 400, top: 20 },
    c: { id: "c", left: 600, top: 40 },
  })
})

test("the size only takes the offered levels", () => {
  let s = state([])
  assert.equal(s.zoom, 1)
  s = reducer(s, { type: "ZOOM", zoom: 0.7 })
  assert.equal(s.zoom, 0.7)
  s = reducer(s, { type: "ZOOM", zoom: 0.3 })
  assert.equal(s.zoom, 0.7)
  s = reducer(s, { type: "ZOOM", zoom: undefined })
  assert.equal(s.zoom, 0.7)
})

test("removing the running activity stops the timer", () => {
  const s = state([{ id: "a" }, { id: "b" }], {
    current: { id: "a", startedAt: 0 },
  })
  assert.equal(reducer(s, { type: "REMOVE_ACTIVITY", id: "b" }).current.id, "a")
  const after = reducer(s, { type: "REMOVE_ACTIVITY", id: "a" })
  assert.equal(after.current, null)
  assert.deepEqual(Object.keys(after.activities), ["b"])
})

test("placing activities sets the given positions", () => {
  const before = state([
    { id: "a", left: 23, top: 41 },
    { id: "b", left: 300, top: 40 },
  ])
  const after = reducer(before, {
    type: "PLACE_ACTIVITIES",
    positions: { a: { left: 20, top: 20 }, removed: { left: 0, top: 0 } },
  })
  assert.deepEqual(after.activities, {
    a: { id: "a", left: 20, top: 20 },
    b: { id: "b", left: 300, top: 40 },
  })
})
