/* global $ */
function _sel(sel) {
  return document.querySelector(sel)
}

/* eslint-disable-next-line */
function _cl(el, cl, add) {
  el.classList[add ? "add" : "remove"](cl)
}

function doSubmit(el) {
  el.closest("form").requestSubmit()
}

$(() => {
  const gettext =
    window.gettext ||
    function (t) {
      return t
    }

  // AJAX modals
  const dismissModals = function () {
    // LOL, dismiss.
    $(".modal, .modal-backdrop").remove()
    $(document.body).removeClass("modal-open").removeAttr("style")
  }

  const initModal = function (data) {
    dismissModals()

    const $data = $(data)

    $data.modal({
      backdrop: $data.find("form[method=post]").length ? "static" : true,
    })

    setTimeout(() => {
      const fields = $(".modal").find("input, select")
      if (fields.filter("[autofocus]").length) {
        fields.filter("[autofocus]").focus()
      } else {
        fields.filter(":visible").first().focus()
      }
    }, 100)

    initWidgets()
  }

  window.initModal = initModal
  window.openModalFromUrl = function (url) {
    $.ajax({
      url,
      success(data) {
        initModal(data)
      },
      error() {
        alert(gettext("Unable to open the form"))
      },
      xhrFields: {
        withCredentials: true,
      },
    })
  }

  $(document.body).on("click", "[data-toggle]", function (event) {
    if (this.dataset.toggle == "ajaxmodal") {
      event.preventDefault()
      window.openModalFromUrl(this.href)
    }
  })

  $(document.body).on("submit", ".modal-dialog form", function (_event) {
    if (this.method.toLowerCase() == "post") {
      const action = this.action,
        data = $(this).serialize()
      this.parentNode.removeChild(this)
      $.post(action, data, (data, status, jqXHR) => {
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
        */
        ) => {
          initModal(data)
        }
      )
    }
    return false
  })

  // Autosubmit forms
  $(document.body).on(
    "change",
    "form[data-autosubmit] select, form[data-autosubmit] input",
    function () {
      if (this.form.method != "get") {
        doSubmit(this.form)
        return
      }

      const fd = new FormData(this.form)
      let params = new URLSearchParams()
      for (let part of fd) {
        if (part[1]) params.append(part[0], part[1])
      }
      params.sort()
      params = params.toString()
      window.location.href = params ? `?${params}` : "."
    }
  )

  // Search form restoration
  $(".form-search").each(() => {
    let params = new URLSearchParams(window.location.search.slice(1))
    // Also see workbench/generic.py
    ;["disposition", "error", "export", "page"].forEach((key) =>
      params.delete(key)
    )
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
      if (el.dataset.toggle == "ajaxmodal") {
        window.openModalFromUrl(el.href)
      } else {
        window.location.href = el.href
      }
    } else {
      window.console && window.console.log(e, e.keyCode)
      return
    }

    return false
  })

  // Widgets
  initWidgets()

  // Some special cases...
  $(document.body).on("click", "[data-hours-button]", function () {
    this.blur()
    const value = prompt(this.dataset.hoursButton)
    if (parseFloat(value)) {
      $("#id_modal-days")
        .val((parseFloat(value) / 8).toFixed(2))
        .focus()
    }
  })

  $(document.body).on("click", "[data-multiply-cost]", function (e) {
    e.preventDefault()
    const factor = parseFloat(this.dataset.multiplyCost),
      tpc = parseFloat($("#id_modal-third_party_costs").val()),
      cost = $("#id_modal-cost")

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
      this.closest(".widget--checkboxselectmultiple").querySelectorAll("input")
    )
    inputs.forEach((el) => (el.checked = arr.includes(el.value)))
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
        new Date(invoicedOn.val()).getTime() + 14 * 86400 * 1000
      )
      dueOn.val(
        `${addZero(due.getFullYear())}-${addZero(1 + due.getMonth())}-${addZero(
          due.getDate()
        )}`
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
        new Date(offeredOn.val()).getTime() + 59 * 86400 * 1000
      )
      validUntil.val(
        `${addZero(day.getFullYear())}-${addZero(1 + day.getMonth())}-${addZero(
          day.getDate()
        )}`
      )
    })
  }

  $("[data-autofill]:not(.initialized)").each(function () {
    const self = $(this),
      data = self.data("autofill"),
      sel = self.find("select")

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
    const self = $(this),
      url = self.data("autocomplete-url"),
      id = self.data("autocomplete-id"),
      input = $(`#${id}`)

    self
      .addClass("initialized")
      .autocomplete({
        minLength: 2,
        source(request, response) {
          $.get(url, { q: request.term }, (data) => {
            response(data.results)
          })
        },
        focus(event, ui) {
          self.val(ui.item.label)
          return false
        },
        select(event, ui) {
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
      $("#id_modal-third_party_costs").val(data.cost)
    })
  })

  $("[data-offer-form]").each(function () {
    const form = this
    // const form = $(this)
    //
    const read = (sel, root = document) =>
      parseFloat(root.querySelector(sel).value) || 0
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
      const liableToVat = document.querySelector("#id_liable_to_vat").checked
      const totalExclTax = offerCost - discount
      const total = totalExclTax * (liableToVat ? 1.077 : 1)

      write("#id_subtotal", offerCost)
      write("#id_total_excl_tax", totalExclTax)
      write("#id_total", total)
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
}

window.addInlineForm = function addInlineForm(slug, onComplete) {
  const totalForms = $(`#id_${slug}-TOTAL_FORMS`),
    newId = parseInt(totalForms.val(), 10) || 0

  totalForms.val(newId + 1)
  const empty = $(`#${slug}-empty`),
    attributes = ["id", "name", "for"],
    form = $(empty.html())

  form.removeClass("empty").attr("id", `${slug}-${newId}`)

  for (let i = 0; i < attributes.length; ++i) {
    const attr = attributes[i]

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
