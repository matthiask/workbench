import assert from "node:assert/strict"
import { test } from "node:test"

import { deserialize } from "./store.js"

test("stored states of all versions load", () => {
  const v1 = deserialize(
    JSON.stringify({ _v: 1, activities: [{ id: "a", color: "#123456" }] }),
  )
  assert.deepEqual(v1.activities, { a: { id: "a", color: "#123456" } })

  const v4 = deserialize(
    JSON.stringify({
      _v: 4,
      activities: { a: { id: "a" }, null: { id: null } },
      modalActivity: "a",
      zoom: 0.8,
    }),
  )
  // Uncolored activities get the default, a stale modal isn't restored
  assert.deepEqual(v4.activities, { a: { id: "a", color: "#ffffff" } })
  assert.equal(v4.modalActivity, undefined)
  assert.equal(v4.zoom, 0.8)
})

test("unknown states are dropped", () => {
  assert.deepEqual(deserialize(JSON.stringify({ activities: {} })), {
    activities: {},
  })
  assert.deepEqual(deserialize(JSON.stringify({ _v: 99, zoom: 0.8 })), {
    activities: {},
  })
})
