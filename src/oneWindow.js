import {createIdentifier} from "./utils.js"

const STORAGE_KEY = "one-window"

export function initOneWindow() {
  const ident = createIdentifier()
  localStorage.setItem(STORAGE_KEY, ident)

  window.addEventListener("storage", e => {
    if (e.key === STORAGE_KEY) {
      document.write("<h1>Only one window allowed at a time</h1>")
    }
  })
}
