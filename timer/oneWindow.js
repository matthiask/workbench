import { createIdentifier } from "./utils.js"

const STORAGE_KEY = "one-window"

export function initOneWindow() {
  const ident = createIdentifier()
  localStorage.setItem(STORAGE_KEY, ident)

  window.addEventListener("storage", (e) => {
    if (e.key === STORAGE_KEY) {
      // biome-ignore lint/correctness/noSelfAssign: Remove all behaviors
      document.body.innerHTML = document.body.innerHTML
      document.querySelector('div[role="main"]').classList.add("deactivated")
    }
  })
}
