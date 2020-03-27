import {createIdentifier} from "./utils.js"

const STORAGE_KEY = "one-window"

export function initOneWindow() {
  const ident = createIdentifier()
  localStorage.setItem(STORAGE_KEY, ident)

  window.addEventListener("storage", (e) => {
    if (e.key === STORAGE_KEY) {
      /* eslint-disable-next-line */
      document.body.innerHTML = document.body.innerHTML // Remove all behaviors
      document.querySelector('div[role="main"]').classList.add("deactivated")
    }
  })
}
