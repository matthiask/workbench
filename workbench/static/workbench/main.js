import * as bootstrap from "bootstrap"
import Sortable from "sortablejs"
import "@fontsource-variable/inter"
import "./main.scss"

window.bootstrap = bootstrap

function _sel(sel) {
  return document.querySelector(sel)
}

// Dark mode functionality
function initDarkMode() {
  const getStoredTheme = () => window.localStorage.getItem("theme")
  const setStoredTheme = (theme) => {
    if (theme === "auto") {
      window.localStorage.removeItem("theme")
    } else {
      window.localStorage.setItem("theme", theme)
    }
  }

  const getSystemTheme = () => {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light"
  }

  const getThemeMode = () => {
    const storedTheme = getStoredTheme()
    return storedTheme || "auto"
  }

  const setTheme = (mode) => {
    const activeTheme = mode === "auto" ? getSystemTheme() : mode
    document.documentElement.setAttribute("data-bs-theme", activeTheme)
    updateThemeButton(mode)
  }

  const updateThemeButton = (mode) => {
    const button = _sel("[data-theme-toggle]")
    if (!button) return

    const icon = button.querySelector("svg")
    if (!icon) return

    // Update icon and title based on mode
    if (mode === "light") {
      icon.innerHTML = `<path d="M8 11a3 3 0 1 1 0-6 3 3 0 0 1 0 6zm0 1a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM8 0a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 0zm0 13a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 13zm8-5a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2a.5.5 0 0 1 .5.5zM3 8a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2A.5.5 0 0 1 3 8zm10.657-5.657a.5.5 0 0 1 0 .707l-1.414 1.415a.5.5 0 1 1-.707-.708l1.414-1.414a.5.5 0 0 1 .707 0zm-9.193 9.193a.5.5 0 0 1 0 .707L3.05 13.657a.5.5 0 0 1-.707-.707l1.414-1.414a.5.5 0 0 1 .707 0zm9.193 2.121a.5.5 0 0 1-.707 0l-1.414-1.414a.5.5 0 0 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .707zM4.464 4.465a.5.5 0 0 1-.707 0L2.343 3.05a.5.5 0 1 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .708z"/>`
      button.setAttribute("title", "Theme: Light")
    } else if (mode === "dark") {
      icon.innerHTML = `<path d="M6 .278a.768.768 0 0 1 .08.858 7.208 7.208 0 0 0-.878 3.46c0 4.021 3.278 7.277 7.318 7.277.527 0 1.04-.055 1.533-.16a.787.787 0 0 1 .81.316.733.733 0 0 1-.031.893A8.349 8.349 0 0 1 8.344 16C3.734 16 0 12.286 0 7.71 0 4.266 2.114 1.312 5.124.06A.752.752 0 0 1 6 .278zM4.858 1.311A7.269 7.269 0 0 0 1.025 7.71c0 4.02 3.279 7.276 7.319 7.276a7.316 7.316 0 0 0 5.205-2.162c-.337.042-.68.063-1.029.063-4.61 0-8.343-3.714-8.343-8.29 0-1.167.242-2.278.681-3.286z"/>`
      button.setAttribute("title", "Theme: Dark")
    } else {
      // auto mode
      icon.innerHTML = `<path d="M8 15A7 7 0 1 0 8 1v14zm0 1A8 8 0 1 1 8 0a8 8 0 0 1 0 16z"/>`
      button.setAttribute("title", "Theme: Auto")
    }
  }

  const cycleTheme = () => {
    const currentMode = getThemeMode()
    let newMode

    // Cycle: auto -> light -> dark -> auto
    if (currentMode === "auto") {
      newMode = "light"
    } else if (currentMode === "light") {
      newMode = "dark"
    } else {
      newMode = "auto"
    }

    setStoredTheme(newMode)
    setTheme(newMode)
  }

  // Set theme on page load
  setTheme(getThemeMode())

  // Listen for theme toggle button clicks
  document.body.addEventListener("click", (e) => {
    const button = e.target.closest("[data-theme-toggle]")
    if (button) {
      e.preventDefault()
      cycleTheme()
    }
  })

  // Watch for system theme changes (only matters in auto mode)
  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", () => {
      const mode = getThemeMode()
      if (mode === "auto") {
        setTheme("auto")
      }
    })
}

// Initialize dark mode as early as possible
initDarkMode()

function doSubmit(el) {
  el.closest("form").requestSubmit()
}

// Delegated event listener, the handler receives the matching element
function on(type, selector, handler) {
  document.addEventListener(type, (e) => {
    const el = e.target.closest?.(selector)
    if (el) handler(e, el)
  })
}

function setValue(el, value, { change = false } = {}) {
  if (!el) return
  el.value = value
  if (change) el.dispatchEvent(new Event("change", { bubbles: true }))
}

function isoDate(date) {
  const pad = (num) => `${num}`.padStart(2, "0")
  return `${date.getFullYear()}-${pad(1 + date.getMonth())}-${pad(date.getDate())}`
}

function debounce(func, wait) {
  let timeout
  return (...args) => {
    clearTimeout(timeout)
    timeout = setTimeout(() => func(...args), wait)
  }
}

const gettext = (t) => (window.gettext || ((t) => t))(t)

// AJAX modals
function dismissModals() {
  for (const el of document.querySelectorAll(".modal, .modal-backdrop")) {
    el.remove()
  }
  document.body.classList.remove("modal-open")
  document.body.removeAttribute("style")
}

function initModal(html) {
  dismissModals()

  const div = document.createElement("div")
  div.innerHTML = html
  const el = div.querySelector(".modal")
  if (el) {
    document.body.append(div)
    const form = div.querySelector("form[method=post]")
    const modal = new bootstrap.Modal(el, {
      backdrop: form ? "static" : true,
      // Forms only close on escape as long as nothing has been changed
      keyboard: !form,
    })
    el.addEventListener("hide.bs.modal", () => {
      div.remove()
    })
    modal.show()

    if (form) {
      const serialize = () => new URLSearchParams(new FormData(form)).toString()
      let initial = null
      el.addEventListener("keydown", (e) => {
        if (e.key !== "Escape" || e.defaultPrevented) return
        if (initial === null || serialize() === initial) {
          modal.hide()
        } else {
          // The same hint as Bootstrap's for static backdrops
          el.classList.add("modal-static")
          setTimeout(() => el.classList.remove("modal-static"), 300)
        }
      })
      // Widgets may set values while initializing
      setTimeout(() => {
        initial = serialize()
      }, 100)
    }

    setTimeout(() => {
      // Force a focus on first autofocus element
      for (const input of el.querySelectorAll("[autofocus]")) {
        input.focus()
        return
      }

      // Else find first input or select field which isn't a child of a
      // hidden element.
      for (const input of el.querySelectorAll(
        ":is(input, select):not([type=hidden])",
      )) {
        if (!input.closest(".d-none")) {
          input.focus()
          return
        }
      }
    }, 100)
  }

  initWidgets()
}

// Bootstrap focuses the modal and listens for the escape key on it, which
// only works if the modal is focusable
document.addEventListener("show.bs.modal", (e) => {
  if (!e.target.hasAttribute("tabindex")) e.target.tabIndex = -1
})

// The views answer differently to requests made by JavaScript (request.is_ajax())
const AJAX_HEADERS = { "x-requested-with": "XMLHttpRequest" }

window.initModal = initModal
window.openModalFromUrl = (url) => {
  fetch(url, { credentials: "include", headers: AJAX_HEADERS })
    .then((response) => response.text())
    .then((html) => {
      initModal(html)
    })
    .catch((e) => {
      console.error(e)
      alert(gettext("Unable to open the form"))
    })
}

on("click", "[data-ajaxmodal]", (e, el) => {
  e.preventDefault()
  window.openModalFromUrl(el.href)
})

on("submit", ".modal-dialog form", async (e, form) => {
  e.preventDefault()
  const action = form.action
  try {
    if (form.method.toLowerCase() !== "post") {
      const params = new URLSearchParams(new FormData(form))
      const response = await fetch(`${action}?${params}`, {
        headers: AJAX_HEADERS,
      })
      initModal(await response.text())
      return
    }

    const body = new FormData(form)
    // Don't submit twice
    form.remove()
    const response = await fetch(action, {
      method: "POST",
      body,
      headers: AJAX_HEADERS,
    })
    // 201 CREATED, 202 ACCEPTED or 204 NO CONTENT
    if ([201, 202, 204].includes(response.status)) {
      document.dispatchEvent(
        new CustomEvent("modalform", {
          detail: { status: response.status, action },
        }),
      )
      dismissModals()
      window.location.reload()
    } else if (response.status === 299) {
      dismissModals()
      const { redirect } = await response.json()
      window.location.href = redirect
      const to = new URL(redirect, window.location.href)
      if (to.pathname === window.location.pathname) {
        // Alternative: window.hashchange -> window.location.reload()
        window.location.reload()
      }
    } else if (response.ok) {
      initModal(await response.text())
    } else {
      throw new Error(`${response.status} ${response.statusText}`)
    }
  } catch (err) {
    console.error(err)
    alert(gettext("Unable to submit the form"))
  }
})

// Autosubmit forms
function autosubmit(_e, el) {
  const form = el.form
  if (form.method !== "get") {
    doSubmit(form)
    return
  }

  const fd = new FormData(form)
  let params = new URLSearchParams()
  for (const part of fd) {
    if (part[1]) params.append(part[0], part[1])
  }
  params.sort()
  params = params.toString()
  window.location.href = params ? `?${params}` : "."
}
on(
  "change",
  "form[data-autosubmit] select, form[data-autosubmit] input:not([type=date])",
  autosubmit,
)
on(
  "change",
  "form[data-autosubmit] input[type=date]",
  debounce(autosubmit, 1000),
)

// Search form restoration
function localStorageKeyFor(href) {
  return `search-${href}`
}

function restoreSearch(href) {
  return href + (window.localStorage.getItem(localStorageKeyFor(href)) || "")
}

// Restore the search params when going through the main menu...
on("click", ".navbar a", (e, el) => {
  if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return
  const href = el.getAttribute("href")
  if (!href) return

  e.preventDefault()
  window.location.href = restoreSearch(href)
})

on("click", "h1, [data-reset-filter]", () => {
  window.localStorage.removeItem(localStorageKeyFor(window.location.pathname))
})

// Hotkeys
document.addEventListener("keydown", (e) => {
  if (/Mac/.test(navigator.platform) ? !e.ctrlKey : !e.altKey) {
    return
  }

  const focus = (sel) => {
    const el = _sel(sel)
    el?.focus()
    el?.select()
  }

  if (e.keyCode === 70) {
    // f
    focus(".form-search input[name=q]")
  } else if (e.keyCode === 72) {
    // h
    window.location.href = "/"
  } else if (e.keyCode === 67 && e.shiftKey) {
    // Shift-c
    window.openModalFromUrl("/contacts/people/select/")
  } else if (e.keyCode === 67) {
    // c
    window.location.href = restoreSearch("/contacts/people/")
  } else if (e.keyCode === 80 && e.shiftKey) {
    // Shift-p
    window.openModalFromUrl("/projects/select/")
  } else if (e.keyCode === 80) {
    // p
    window.location.href = restoreSearch("/projects/")
  } else if (e.keyCode === 79) {
    // o
    window.location.href = restoreSearch("/projects/offers/")
  } else if (e.keyCode === 82) {
    // r
    window.location.href = restoreSearch("/invoices/")
  } else if (e.keyCode === 84) {
    // t
    window.location.href = restoreSearch("/timestamps/")
  } else if (e.keyCode === 68) {
    // d
    window.location.href = restoreSearch("/deals/")
  } else if (e.keyCode === 76) {
    // l
    const el = _sel("[data-createhours]")
    if (e.shiftKey || !el) {
      window.openModalFromUrl("/logbook/hours/create/")
    } else {
      window.openModalFromUrl(el.href)
    }
  } else if (e.keyCode === 75) {
    // k
    const el = _sel("[data-createcost]")
    if (e.shiftKey || !el) {
      window.openModalFromUrl("/logbook/costs/create/")
    } else {
      window.openModalFromUrl(el.href)
    }
  } else if (e.keyCode === 66 && e.shiftKey) {
    // Shift-b
    window.location.href = "/logbook/breaks/"
  } else if (e.keyCode === 66) {
    // b
    window.openModalFromUrl("/logbook/breaks/create/")
  } else if (e.keyCode === 81) {
    // q
    focus(".navbar input[type=search]")
  } else if (e.keyCode === 13) {
    doSubmit(e.target)
  } else if (e.keyCode >= 48 && e.keyCode <= 57) {
    const el = _sel(`[data-number-shortcut="${(e.keyCode - 38) % 10}"]`)
    if (!el) return
    e.preventDefault()
    if ("ajaxmodal" in el.dataset) {
      window.openModalFromUrl(el.href)
    } else {
      window.location.href = el.href
    }
  } else {
    window.console?.log(e, e.keyCode)
    return
  }

  e.preventDefault()
  e.stopPropagation()
})

// Some special cases...
on("click", "[data-hours-button]", (_e, el) => {
  el.blur()
  const value = prompt(el.dataset.hoursButton)
  if (Number.parseFloat(value)) {
    const days = _sel("#id_modal-days")
    setValue(days, (Number.parseFloat(value) / 8).toFixed(2))
    days?.focus()
  }
})

on("click", "[data-multiply-cost]", (e, el) => {
  e.preventDefault()
  const factor = Number.parseFloat(el.dataset.multiplyCost)
  const tpc = Number.parseFloat(_sel("#id_modal-third_party_costs")?.value)
  const cost = _sel("#id_modal-cost")

  if (tpc && factor) {
    setValue(cost, (factor * tpc).toFixed(2))
    cost.focus()
  }
})

on("click", "[data-field-value]", (e, el) => {
  e.preventDefault()
  for (const field of el
    .closest(".form-group")
    .querySelectorAll("input, textarea, select")) {
    setValue(field, el.dataset.fieldValue, { change: true })
  }
})

on("click", "[data-set-period]", (e, el) => {
  e.preventDefault()
  const value = el.dataset.setPeriod.split(":")
  // An empty start keeps the current one, e.g. for "until today"
  if (value[0]) setValue(_sel("#id_date_from"), value[0])
  setValue(_sel("#id_date_until"), value[1], { change: true })
})

on("click", "[data-select-receivers]", (e, el) => {
  e.preventDefault()
  const arr = el.dataset.selectReceivers.split(",")
  for (const input of el
    .closest(".widget--checkboxselectmultiple")
    .querySelectorAll("input")) {
    input.checked = arr.includes(input.value)
  }
})

// "Select all" checkboxes in the group labels of checkbox lists, e.g. the
// services of offers and invoices
on("change", "[data-toggle-following]", (_e, el) => {
  let sibling = el.closest(".form-text").nextElementSibling
  while (sibling && !sibling.matches(".form-text")) {
    for (const input of sibling.querySelectorAll("input")) {
      input.checked = el.checked
    }
    sibling = sibling.nextElementSibling
  }
})

on("click", "[data-pin]", (_e, el) => {
  const url = el.dataset.pin
  fetch(`${url}?pinned=${el.dataset.pinned === "true" ? "" : "pinned"}`)
    .then((r) => r.json())
    .then((data) => {
      el.dataset.pinned = data.pinned
    })
})

on("click", "[data-clear]", (_e, el) => {
  for (const field of document.querySelectorAll(el.dataset.clear)) {
    setValue(field, "", { change: true })
  }
})

on("click", "[data-convert]", async () => {
  const params = new URLSearchParams()
  params.append("day", _sel("#id_modal-rendered_on").value)
  params.append("currency", _sel("#id_modal-expense_currency").value)
  params.append("cost", _sel("#id_modal-expense_cost").value)

  const data = await (await fetch(`/expenses/convert/?${params}`)).json()
  if (data.error) {
    alert(data.error)
  } else {
    setValue(_sel("#id_modal-third_party_costs"), data.cost)
  }
})

on("click", "[data-new-service]", (e, el) => {
  e.preventDefault()
  el.classList.add("invisible")

  // Reset the service dropdown and emit a change event for the progress
  // bar update.
  setValue(_sel("#id_modal-service"), "", { change: true })

  // Show the new-service fields and focus the first input element.
  const container = _sel("#new-service")
  container.classList.remove("d-none")
  container.querySelector("input").focus()
})

on("click", "[data-foreign-currency]", (e, el) => {
  e.preventDefault()
  el.classList.add("invisible")
  _sel("#foreign-currency").classList.remove("d-none")
  _sel("#id_modal-are_expenses").checked = true
})

document.addEventListener("DOMContentLoaded", () => {
  if (_sel(".form-search")) {
    let params = new URLSearchParams(window.location.search.slice(1))
    // Also see workbench/generic.py
    ;["disposition", "error", "export", "page"].forEach((key) => {
      params.delete(key)
    })
    params = params.toString()
    const key = `search-${window.location.pathname}`
    window.localStorage.setItem(key, params ? `?${params}` : "")
  }

  initWidgets()
  initSortableLists()
  initSortableTables()
  initCelebration()
})

function initWidgets() {
  const follow = (from, to, update) => {
    const fromEl = _sel(from)
    const toEl = _sel(to)
    if (fromEl && toEl) {
      fromEl.addEventListener("change", () => update(fromEl, toEl))
    }
  }

  const daysLater = (value, days) =>
    isoDate(new Date(new Date(value).getTime() + days * 86400 * 1000))

  follow("#id_invoiced_on", "#id_due_on", (invoicedOn, dueOn) => {
    dueOn.value = daysLater(invoicedOn.value, 14)
  })
  follow("#id_modal-starts_on", "#id_modal-ends_on", (startsOn, endsOn) => {
    if (!endsOn.value) endsOn.value = startsOn.value
  })
  follow("#id_offered_on", "#id_valid_until", (offeredOn, validUntil) => {
    validUntil.value = daysLater(offeredOn.value, 59)
  })

  for (const el of document.querySelectorAll(
    "[data-autofill]:not(.initialized)",
  )) {
    el.classList.add("initialized")
    const data = JSON.parse(el.dataset.autofill)
    el.querySelector("select").addEventListener("change", (e) => {
      for (const [key, value] of Object.entries(data[e.target.value] || {})) {
        for (const field of el.querySelectorAll(`[name$='${key}']`)) {
          setValue(field, value ?? "")
        }
      }
    })
  }

  for (const el of document.querySelectorAll(
    "[data-autocomplete-id]:not(.initialized)",
  )) {
    el.classList.add("initialized")
    initAutocomplete(el)
  }

  for (const form of document.querySelectorAll("[data-offer-form]")) {
    const read = (sel, root = document) =>
      Number.parseFloat(root.querySelector(sel).value) || 0
    const write = (sel, value, root = document) =>
      (root.querySelector(sel).value = value.toFixed(2))

    function recalculate() {
      let offerCost = 0

      Array.from(form.querySelectorAll("[data-service]")).forEach((service) => {
        const effortRate = read("[data-effort-rate] input", service)
        const effortHours = read("[data-effort-hours] input", service)
        const cost = read("[data-cost] input", service)

        const serviceCost = effortRate * effortHours + cost
        offerCost += serviceCost

        write("[data-service-cost]", serviceCost, service)
      })

      const discount = read("#id_discount")
      const totalExclTax = offerCost - discount

      write("#id_subtotal", offerCost)
      write("#id_total_excl_tax", totalExclTax)
    }

    recalculate()
    form.addEventListener("change", recalculate)
  }

  // Some browsers when set to some languages do not accept decimal values with
  // the point but require a comma (which is annoying). Make all number fields
  // use the en-US locale to work around this misbehavior.
  for (const el of document.querySelectorAll('input[type="number"]')) {
    el.setAttribute("lang", "en-US")
  }

  // The logged hours form has a nice progress bar showing the percentage for each service
  for (const el of document.querySelectorAll("[data-service-progress]")) {
    const select = el.querySelector("select")
    const bars = [...el.querySelectorAll(".progress-bar")]
    const numbers = el.querySelector("[data-numbers]")
    const data = JSON.parse(el.querySelector("script").textContent)

    const update = () => {
      const row = data[select.value]
      const { logged_hours, service_hours } = row || {
        logged_hours: 0,
        service_hours: 0,
      }
      const percentage = service_hours
        ? (100 * logged_hours) / service_hours
        : 0

      const f = percentage > 100 ? 100 / percentage : 1

      bars[0].style.width = `${f * Math.min(75, percentage)}%`
      bars[1].style.width =
        percentage > 75 ? `${f * Math.min(25, percentage - 75)}%` : "0%"
      bars[2].style.width = percentage > 100 ? `${percentage - 100}%` : "0%"

      numbers.textContent = `${logged_hours.toFixed(1)}h / ${service_hours.toFixed(1)}h`
    }

    update()
    select.addEventListener("change", update)
  }
}

// Adds a form to a formset, see workbench/templatetags/formset.py
window.addInlineForm = function addInlineForm(slug) {
  const totalForms = document.getElementById(`id_${slug}-TOTAL_FORMS`)
  const newId = Number.parseInt(totalForms.value, 10) || 0
  totalForms.value = newId + 1

  const empty = document.getElementById(`${slug}-empty`)
  const template = document.createElement("template")
  template.innerHTML = empty.innerHTML.replaceAll("__prefix__", newId)
  const form = template.content.firstElementChild
  form.id = `${slug}-${newId}`

  // Insert the form after the last form (or the template if there are none)
  const forms = [...empty.parentElement.children].filter(
    (el) => el.id === slug || el.id.startsWith(`${slug}-`),
  )
  forms.at(-1).after(form)
  initWidgets()

  return false
}

// Search field filling a hidden input with the ID of the chosen result, see
// Autocomplete in workbench/tools/forms.py
function initAutocomplete(el) {
  const input = document.getElementById(el.dataset.autocompleteId)
  const menu = document.createElement("div")
  menu.className = "dropdown-menu wb-autocomplete"
  el.after(menu)

  let results = []
  let active = -1
  let timeout = null
  let request = 0

  const close = () => {
    menu.classList.remove("show")
    active = -1
  }

  const highlight = (index) => {
    active = index
    menu.querySelectorAll(".dropdown-item").forEach((item, i) => {
      item.classList.toggle("active", i === active)
      if (i === active) item.scrollIntoView({ block: "nearest" })
    })
  }

  const choose = (index) => {
    const result = results[index]
    el.value = result.label
    input.value = result.value
    input.dispatchEvent(new Event("change", { bubbles: true }))
    close()
  }

  const search = async () => {
    const term = el.value.trim()
    const current = ++request
    if (term.length < 2) {
      close()
      return
    }
    const url = new URL(el.dataset.autocompleteUrl, window.location.href)
    url.searchParams.set("q", term)
    const response = await fetch(url)
    if (!response.ok || current !== request) return
    results = (await response.json()).results
    menu.replaceChildren(
      ...results.map((result, index) => {
        const item = document.createElement("button")
        item.type = "button"
        item.className = "dropdown-item"
        item.textContent = result.label
        // Keep the focus in the input until the click has been handled
        item.addEventListener("mousedown", (e) => e.preventDefault())
        item.addEventListener("click", () => choose(index))
        return item
      }),
    )
    active = -1
    menu.classList.toggle("show", results.length > 0)
  }

  el.addEventListener("input", () => {
    clearTimeout(timeout)
    timeout = setTimeout(search, 200)
  })
  el.addEventListener("focus", () => el.select())
  el.addEventListener("blur", close)
  el.addEventListener("keydown", (e) => {
    if (!menu.classList.contains("show")) return
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault()
      const step = e.key === "ArrowDown" ? 1 : -1
      highlight((active + step + results.length) % results.length)
    } else if (e.key === "Enter" && active >= 0) {
      e.preventDefault()
      choose(active)
    } else if (e.key === "Escape") {
      // Don't close the modal too
      e.stopPropagation()
      close()
    }
  })
}

function initSortableLists() {
  // The services of an offer on the project page
  for (const container of document.querySelectorAll(
    "[data-sortable-container]",
  )) {
    Sortable.create(container, {
      draggable: "[data-sortable-item]",
      handle: "[data-sortable-grabber]",
      async onEnd(e) {
        if (e.oldIndex === e.newIndex) return
        const body = new FormData()
        for (const item of container.querySelectorAll("[data-sortable-item]")) {
          body.append("ids", item.dataset.sortableItem)
        }
        const response = await fetch(container.dataset.sortableUrl, {
          method: "POST",
          body,
          headers: {
            "X-CSRFToken": document.cookie.match(/\bcsrftoken=([^;]+)/)[1],
          },
        })
        if (response.ok) {
          window.location.reload()
        } else {
          alert(`${response.status} ${response.statusText}`)
        }
      },
    })
  }

  // Number fields which are renumbered in the order they are dragged into
  for (const form of document.querySelectorAll("[data-renumber]")) {
    const container = form.querySelector(".widget--numberinput")?.parentElement
    if (!container) continue
    Sortable.create(container, {
      draggable: ".widget--numberinput",
      onEnd() {
        container
          .querySelectorAll(".widget--numberinput input")
          .forEach((input, index) => {
            input.value = index + 1
          })
      },
    })
  }
}

function initSortableTables() {
  for (const table of document.querySelectorAll("table[data-sortable]")) {
    const tbody = table.querySelector("tbody")
    const headers = [...table.querySelectorAll("thead th")]

    const parseVal = (cell) => {
      const raw = cell.dataset.sortValue ?? cell.textContent.trim()
      if (!raw) return null
      const num = Number.parseFloat(raw.replace(/[^0-9.-]/g, ""))
      return Number.isNaN(num) ? raw.toLowerCase() : num
    }

    const setIndicator = (th, direction) => {
      th.querySelector(".sort-indicator")?.remove()
      const indicator = document.createElement("span")
      indicator.className = "sort-indicator ms-1 opacity-50"
      indicator.textContent =
        direction === "asc" ? "▲" : direction === "desc" ? "▼" : "⇅"
      if (direction) indicator.classList.remove("opacity-50")
      th.appendChild(indicator)
    }

    let initialTh = null

    for (const th of headers) {
      if (th.hasAttribute("data-no-sort")) continue

      th.style.cursor = "pointer"
      if (th.dataset.sortInitial) {
        th.dataset.sort = th.dataset.sortInitial === "desc" ? "asc" : "desc"
        setIndicator(th, null)
        initialTh = th
      } else {
        setIndicator(th, null)
      }

      const colIndex = headers.indexOf(th)
      th.addEventListener("click", () => {
        const defaultDesc = th.dataset.sortDefault === "desc"
        const currentSort = th.dataset.sort
        const asc = currentSort ? currentSort === "desc" : !defaultDesc

        for (const h of headers) {
          if (h.hasAttribute("data-no-sort")) continue
          delete h.dataset.sort
          setIndicator(h, null)
        }

        th.dataset.sort = asc ? "asc" : "desc"
        setIndicator(th, asc ? "asc" : "desc")

        const absSort = th.hasAttribute("data-sort-abs")
        const sorted = Array.from(tbody.querySelectorAll("tr")).sort((a, b) => {
          let aVal = parseVal(a.cells[colIndex])
          let bVal = parseVal(b.cells[colIndex])
          if (aVal === null) return 1
          if (bVal === null) return -1
          if (typeof aVal === "number" && typeof bVal === "number") {
            if (absSort) {
              aVal = Math.abs(aVal)
              bVal = Math.abs(bVal)
            }
            return asc ? aVal - bVal : bVal - aVal
          }
          return asc
            ? String(aVal).localeCompare(String(bVal))
            : String(bVal).localeCompare(String(aVal))
        })
        for (const row of sorted) tbody.appendChild(row)
      })
    }

    if (initialTh) initialTh.click()
  }
}

function initCelebration() {
  const el = _sel(".celebration")
  if (!el) return

  // Let the hours rings grow from their value before logging
  for (const name of ["today", "week"]) {
    const from = el.dataset[`ringFrom${name[0].toUpperCase()}${name.slice(1)}`]
    if (from === undefined) continue
    for (const fill of document.querySelectorAll(
      `[data-hours-ring="${name}"] .hours-ring-fill`,
    )) {
      const to = fill.style.strokeDasharray
      fill.style.transition = "none"
      fill.style.strokeDasharray = `${from} 100`
      window.getComputedStyle(fill).strokeDasharray // Force a style flush
      fill.style.transition = ""
      requestAnimationFrame(() => {
        fill.style.strokeDasharray = to
      })
    }
  }

  if (
    el.hasAttribute("data-confetti") &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches
  ) {
    const colors = ["#f47c3c", "#325d88", "#93c54b", "#f1e53b", "#d9534f"]
    for (let i = 0; i < 40; ++i) {
      const piece = document.createElement("span")
      const angle = Math.random() * 2 * Math.PI
      const distance = 6 + Math.random() * 14
      piece.className = "confetti"
      piece.style.setProperty("--x", `${Math.cos(angle) * distance}rem`)
      piece.style.setProperty("--y", `${Math.sin(angle) * distance}rem`)
      piece.style.setProperty("--r", `${Math.random() * 720 - 360}deg`)
      piece.style.background = colors[i % colors.length]
      el.appendChild(piece)
    }
  }

  setTimeout(() => el.remove(), 3000)
}

// Clamped descriptions expand when clicked
document.addEventListener("click", (e) => {
  const clamp = e.target.closest("[data-clamp]")
  if (clamp && !e.target.closest("a")) clamp.classList.add("is-expanded")
})
