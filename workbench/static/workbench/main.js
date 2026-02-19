import * as bootstrap from "bootstrap"
import "./main.scss"

window.bootstrap = bootstrap

/* global $ */
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

$(() => {
  const gettext = window.gettext || ((t) => t)

  // AJAX modals
  const dismissModals = () => {
    // LOL, dismiss.
    $(".modal, .modal-backdrop").remove()
    $(document.body).removeClass("modal-open").removeAttr("style")
  }

  const initModal = (data) => {
    dismissModals()

    const div = document.createElement("div")
    div.innerHTML = data
    const el = div.querySelector(".modal")
    if (el) {
      document.body.append(div)
      const modal = new bootstrap.Modal(el, {
        backdrop: div.querySelector("form[method=post]") ? "static" : true,
      })
      el.addEventListener("hide.bs.modal", () => {
        div.remove()
      })
      modal.show()

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

  window.initModal = initModal
  window.openModalFromUrl = (url) => {
    fetch(url, {
      credentials: "include",
      headers: { "x-requested-with": "XMLHttpRequest" },
    })
      .then((response) => response.text())
      .then((html) => {
        initModal(html)
      })
      .catch((e) => {
        console.error(e)
        alert(gettext("Unable to open the form"))
      })
  }

  document.body.addEventListener("click", (e) => {
    const el = e.target.closest("[data-ajaxmodal]")
    if (el) {
      e.preventDefault()
      window.openModalFromUrl(el.href)
    }
  })

  $(document.body).on("submit", ".modal-dialog form", function (_event) {
    if (this.method.toLowerCase() === "post") {
      const action = this.action
      const data = $(this).serialize()
      this.parentNode.removeChild(this)
      $.post(action, data, (data, _status, jqXHR) => {
        // 201 CREATED, 202 ACCEPTED or 204 NO CONTENT
        if (
          jqXHR.status === 201 ||
          jqXHR.status === 202 ||
          jqXHR.status === 204
        ) {
          $(document).trigger("modalform", [jqXHR.status, action])
          dismissModals()
          window.location.reload()
        } else if (jqXHR.status === 299) {
          dismissModals()

          window.location.href = data.redirect
          const to = new URL(data.redirect, window.location.href)
          if (to.pathname === window.location.pathname) {
            // Alternative: window.hashchange -> window.location.reload()
            window.location.reload()
          }
        } else {
          initModal(data)
        }
      })
    } else {
      $.get(
        `${this.action}?${$(this).serialize()}`,
        (
          data /*,
        status,
        jqXHR
        */,
        ) => {
          initModal(data)
        },
      )
    }
    return false
  })

  // Autosubmit forms
  function autosubmit(e) {
    const form = e.target.form
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
  $(document.body).on(
    "change",
    "form[data-autosubmit] select, form[data-autosubmit] input:not([type=date])",
    autosubmit,
  )

  function debounce(func, wait, immediate) {
    // 'private' variable for instance
    // The returned function will be able to reference this due to closure.
    // Each call to the returned function will share this common timer.
    let timeout

    // Calling debounce returns a new anonymous function
    return function (...args) {
      // Should the function be called now? If immediate is true
      //   and not already in a timeout then the answer is: Yes
      const callNow = immediate && !timeout

      // This is the basic debounce behaviour where you can call this
      //   function several times, but it will only execute once
      //   [before or after imposing a delay].
      //   Each time the returned function is called, the timer starts over.
      clearTimeout(timeout)

      // Set the new timeout
      timeout = setTimeout(() => {
        // Inside the timeout function, clear the timeout variable
        // which will let the next execution run when in 'immediate' mode
        timeout = null

        // Check if the function already ran with the immediate flag
        if (!immediate) {
          // Call the original function with apply
          // apply lets you define the 'this' object as well as the arguments
          //    (both captured before setTimeout)
          func.apply(this, args)
        }
      }, wait)

      // Immediate mode and no wait timer? Execute the function..
      if (callNow) func.apply(this, args)
    }
  }

  $(document.body).on(
    "change",
    "form[data-autosubmit] input[type=date]",
    debounce(autosubmit, 1000),
  )

  // Search form restoration
  $(".form-search").each(() => {
    let params = new URLSearchParams(window.location.search.slice(1))
    // Also see workbench/generic.py
    ;["disposition", "error", "export", "page"].forEach((key) => {
      params.delete(key)
    })
    params = params.toString()
    const key = `search-${window.location.pathname}`
    window.localStorage.setItem(key, params ? `?${params}` : "")
  })

  function localStorageKeyFor(href) {
    return `search-${href}`
  }

  function restoreSearch(href) {
    return href + (window.localStorage.getItem(localStorageKeyFor(href)) || "")
  }

  // Restore the search params when going through the main menu...
  $(".navbar").on("click", "a", function (e) {
    const orig = e.originalEvent
    if (orig.altKey || orig.ctrlKey || orig.metakey || orig.shiftKey) return

    e.preventDefault()
    window.location.href = restoreSearch(this.getAttribute("href"))
  })

  $("h1, [data-reset-filter]").on("click", () => {
    window.localStorage.removeItem(localStorageKeyFor(window.location.pathname))
  })

  // Hotkeys
  $(document.body).on("keydown", (e) => {
    if (/Mac/.test(navigator.platform) ? !e.ctrlKey : !e.altKey) {
      return
    }

    if (e.keyCode === 70) {
      // f
      $(".form-search input[name=q]").focus().select()
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
      $(".navbar input[type=search]").focus().select()
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

    return false
  })

  // Widgets
  initWidgets()
  initSortableTables()

  // Some special cases...
  $(document.body).on("click", "[data-hours-button]", function () {
    this.blur()
    const value = prompt(this.dataset.hoursButton)
    if (Number.parseFloat(value)) {
      $("#id_modal-days")
        .val((Number.parseFloat(value) / 8).toFixed(2))
        .focus()
    }
  })

  $(document.body).on("click", "[data-multiply-cost]", function (e) {
    e.preventDefault()
    const factor = Number.parseFloat(this.dataset.multiplyCost)
    const tpc = Number.parseFloat($("#id_modal-third_party_costs").val())
    const cost = $("#id_modal-cost")

    if (tpc && factor) {
      cost.val((factor * tpc).toFixed(2)).focus()
    }
  })

  $(document.body).on("click", "[data-field-value]", function (e) {
    e.preventDefault()
    const field = $(this).closest(".form-group").find("input, textarea, select")
    field.val(this.dataset.fieldValue)
    field.trigger("change")
  })

  $(document.body).on("click", "[data-set-period]", function (e) {
    e.preventDefault()
    const value = this.dataset.setPeriod.split(":")
    $("#id_date_from").val(value[0])
    $("#id_date_until").val(value[1]).trigger("change")
  })

  $(document.body).on("click", "[data-select-receivers]", function (e) {
    e.preventDefault()
    const arr = this.dataset.selectReceivers.split(",")
    const inputs = Array.from(
      this.closest(".widget--checkboxselectmultiple").querySelectorAll("input"),
    )
    inputs.forEach((el) => {
      el.checked = arr.includes(el.value)
    })
  })

  $(document.body).on("click", "[data-pin]", (e) => {
    const url = e.target.dataset.pin
    fetch(`${url}?pinned=${e.target.dataset.pinned === "true" ? "" : "pinned"}`)
      .then((r) => r.json())
      .then((data) => (e.target.dataset.pinned = data.pinned))
  })

  document.body.addEventListener("click", (e) => {
    let el = e.target.closest("[data-new-service]")
    if (el) {
      e.preventDefault()
      el.classList.add("invisible")

      // Reset the service dropdown and emit a change event for the progress
      // bar update.
      const select = _sel("#id_modal-service")
      select.value = ""
      select.dispatchEvent(new InputEvent("change", { bubbles: true }))

      // Show the new-service fields and focus the first input element.
      const container = _sel("#new-service")
      container.classList.remove("d-none")
      container.querySelector("input").focus()
    }

    el = e.target.closest("[data-foreign-currency]")
    if (el) {
      e.preventDefault()
      el.classList.add("invisible")
      _sel("#foreign-currency").classList.remove("d-none")
      _sel("#id_modal-are_expenses").checked = true
    }
  })
})

function initWidgets() {
  function addZero(num) {
    return num < 10 ? `0${num}` : `${num}`
  }

  const invoicedOn = $("#id_invoiced_on")
  const dueOn = $("#id_due_on")
  if (invoicedOn.length && dueOn.length) {
    invoicedOn.on("change", (_event) => {
      const due = new Date(
        new Date(invoicedOn.val()).getTime() + 14 * 86400 * 1000,
      )
      dueOn.val(
        `${addZero(due.getFullYear())}-${addZero(1 + due.getMonth())}-${addZero(
          due.getDate(),
        )}`,
      )
    })
  }

  const startsOn = $("#id_modal-starts_on")
  const endsOn = $("#id_modal-ends_on")
  if (startsOn.length && endsOn.length) {
    startsOn.on("change", () => {
      if (!endsOn.val()) endsOn.val(startsOn.val())
    })
  }

  const offeredOn = $("#id_offered_on")
  const validUntil = $("#id_valid_until")
  if (offeredOn.length && validUntil.length) {
    offeredOn.on("change", (_event) => {
      const day = new Date(
        new Date(offeredOn.val()).getTime() + 59 * 86400 * 1000,
      )
      validUntil.val(
        `${addZero(day.getFullYear())}-${addZero(1 + day.getMonth())}-${addZero(
          day.getDate(),
        )}`,
      )
    })
  }

  $("[data-autofill]:not(.initialized)").each(function () {
    const self = $(this)
    const data = self.data("autofill")
    const sel = self.find("select")

    self.addClass("initialized")
    sel.on("change", function () {
      if (data[`${this.value}`]) {
        $.each(data[`${this.value}`], (key, value) => {
          self.find(`[name$='${key}']`).val(value)
        })
      }
    })
  })

  $("[data-autocomplete-id]:not(.initialized)").each(function () {
    const self = $(this)
    const url = self.data("autocomplete-url")
    const id = self.data("autocomplete-id")
    const input = $(`#${id}`)

    self
      .addClass("initialized")
      .autocomplete({
        minLength: 2,
        source(request, response) {
          $.get(url, { q: request.term }, (data) => {
            response(data.results)
          })
        },
        focus(_event, ui) {
          self.val(ui.item.label)
          return false
        },
        select(_event, ui) {
          self.val(ui.item.label)
          input.val(ui.item.value).trigger("change")
          return false
        },
      })
      .on("focus", function () {
        this.select()
      })
  })

  $(document.body).on("click", "[data-clear]", function () {
    $(this.dataset.clear).val("").trigger("change")
  })

  $(document.body).on("click", "[data-convert]", () => {
    const params = new URLSearchParams()
    params.append("day", $("#id_modal-rendered_on").val())
    params.append("currency", $("#id_modal-expense_currency").val())
    params.append("cost", $("#id_modal-expense_cost").val())
    console.log(params)
    console.log(params.toString())

    $.getJSON(`/expenses/convert/?${params.toString()}`, (data) => {
      if (data.error) {
        alert(data.error)
      } else {
        $("#id_modal-third_party_costs").val(data.cost)
      }
    })
  })

  $("[data-offer-form]").each(function () {
    const form = this
    // const form = $(this)
    //
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
  })

  // Some browsers when set to some languages do not accept decimal values with
  // the point but require a comma (which is annoying). Make all number fields
  // use the en-US locale to work around this misbehavior.
  $('input[type="number"]').each(function () {
    this.setAttribute("lang", "en-US")
  })

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

window.addInlineForm = function addInlineForm(slug, onComplete) {
  const totalForms = $(`#id_${slug}-TOTAL_FORMS`)
  const newId = Number.parseInt(totalForms.val(), 10) || 0

  totalForms.val(newId + 1)
  const empty = $(`#${slug}-empty`)
  const attributes = ["id", "name", "for"]
  const form = $(empty.html())

  form.removeClass("empty").attr("id", `${slug}-${newId}`)

  for (const attr of attributes) {
    form.find(`*[${attr}*=__prefix__]`).each(function () {
      const el = $(this)
      el.attr(attr, el.attr(attr).replace(/__prefix__/, newId))
    })
  }

  // insert the form after the last sibling with the same tagName
  // cannot use siblings() here, because the empty element may be the
  // only one (if no objects exist until now)
  form
    .insertAfter(empty.parent().children(`[id|=${slug}]:last`))
    .hide()
    .fadeIn()

  if (onComplete) onComplete(form)

  return false
}

function initSortableTables() {
  for (const table of document.querySelectorAll("table[data-sortable]")) {
    const tbody = table.querySelector("tbody")
    const headers = [...table.querySelectorAll("thead th")]

    const parseVal = (cell) => {
      const text = cell.textContent.trim()
      if (!text) return null
      const num = Number.parseFloat(text)
      return Number.isNaN(num) ? text.toLowerCase() : num
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

    for (const th of headers) {
      if (th.hasAttribute("data-no-sort")) continue

      th.style.cursor = "pointer"
      if (th.dataset.sortInitial) {
        th.dataset.sort = th.dataset.sortInitial
        setIndicator(th, th.dataset.sortInitial)
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

        const sorted = Array.from(tbody.querySelectorAll("tr")).sort((a, b) => {
          const aVal = parseVal(a.cells[colIndex])
          const bVal = parseVal(b.cells[colIndex])
          if (aVal === null) return 1
          if (bVal === null) return -1
          if (typeof aVal === "number" && typeof bVal === "number") {
            return asc ? aVal - bVal : bVal - aVal
          }
          return asc
            ? String(aVal).localeCompare(String(bVal))
            : String(bVal).localeCompare(String(aVal))
        })
        for (const row of sorted) tbody.appendChild(row)
      })
    }
  }
}
