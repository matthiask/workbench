$(function() {
  // AJAX modals
  var dismissModals = function() {
    // LOL, dismiss.
    $(".modal, .modal-backdrop").remove()
    $(document.body)
      .removeClass("modal-open")
      .removeAttr("style")
  }

  var initModal = function(data) {
    dismissModals()

    $(data).modal()

    setTimeout(function() {
      var fields = $(".modal").find("input, select")
      if (fields.filter("[autofocus]").length) {
        fields.filter("[autofocus]").focus()
      } else {
        fields
          .filter(":visible")
          .first()
          .focus()
      }
    }, 500)

    initWidgets()
  }

  window.openModalFromUrl = function(url) {
    $.get(url, function(data) {
      initModal(data)
    })
  }

  $(document.body).on("click", "[data-toggle]", function(event) {
    if (this.dataset.toggle == "ajaxmodal") {
      event.preventDefault()
      window.openModalFromUrl(this.href)
    }
  })

  $(document.body).on("submit", ".modal-dialog form", function(_event) {
    if (this.method.toLowerCase() == "post") {
      const action = this.action
      $.post(action, $(this).serialize(), function(data, status, jqXHR) {
        // 201 CREATED, 202 ACCEPTED or 204 NO CONTENT
        if (
          jqXHR.status === 201 ||
          jqXHR.status === 202 ||
          jqXHR.status === 204
        ) {
          $(document).trigger("modalform", [jqXHR.status, action])
          dismissModals()
          window.location.reload()
        } else {
          initModal(data)
        }
      })
    } else {
      $.get(this.action + "?" + $(this).serialize(), function(
        data /*,
        status,
        jqXHR
        */
      ) {
        initModal(data)
      })
    }
    return false
  })

  $(document.body).on("submit", "form[data-ajaxform]", function(event) {
    event.preventDefault()
    var form = this

    $.post(form.action, $(form).serialize(), function(data, status, jqXHR) {
      // 201 CREATED, 202 ACCEPTED or 204 NO CONTENT
      if (
        jqXHR.status === 201 ||
        jqXHR.status === 202 ||
        jqXHR.status === 204
      ) {
        // Fine!
        $("button", form).text("OK!")
      } else {
        alert("Saving failed!")
      }
    })
  })

  // Search forms
  $(".form-search").on("change", "select, input", function() {
    $(this)
      .closest("form")
      .submit()
  })

  $(".form-search").each(function() {
    if (window.location.search) {
      const key = `search-${window.location.pathname}`
      window.localStorage.setItem(
        key,
        /\be=1\b/.test(window.location.search) ? "" : window.location.search
      )
    }
  })

  // Restore the search params when going through the main menu...
  $(".navbar").on("click", "a", function(e) {
    const key = `search-${this.getAttribute("href")}`
    const search = window.localStorage.getItem(key)
    if (search) {
      e.preventDefault()
      window.location.href = this.getAttribute("href") + search
    }
  })

  // ... and always remove the saved search params when clicking on an h1
  $("h1").on("click", "a", function() {
    const key = `search-${this.getAttribute("href")}`
    window.localStorage.removeItem(key)
  })

  // Hotkeys
  $(document.body).on("keydown", function(e) {
    if (/Mac/.test(navigator.platform) ? !e.ctrlKey : !e.altKey) {
      return
    }

    if (e.keyCode === 70) {
      // f
      $(".navbar-form input[name=q]")
        .focus()
        .select()
    } else if (e.keyCode === 72) {
      // h
      window.location.href = "/"
    } else if (e.keyCode === 67 && !e.shiftKey) {
      // c
      window.location.href = "/contacts/people/"
    } else if (e.keyCode === 67 && e.shiftKey) {
      // C
      window.location.href = "/contacts/organizations/"
    } else if (e.keyCode === 80) {
      // p
      window.location.href = "/projects/"
    } else if (e.keyCode === 79) {
      // o
      window.location.href = "/offers/"
    } else if (e.keyCode === 82) {
      // r
      window.location.href = "/invoices/"
    } else if (e.keyCode === 65) {
      // a
      window.location.href = "/activities/"
    } else if (e.keyCode === 76) {
      // l
      var el = document.querySelector("[data-createhours]")
      if (el) {
        openModalFromUrl(el.href)
      } else {
        openModalFromUrl("/logbook/create/")
      }
    } else if (e.keyCode === 81) {
      // q
      $(".navbar input[type=search]").focus()
    } else if (e.keyCode === 13) {
      $(e.target)
        .parents("form")
        .submit()
    } else {
      window.console && window.console.log(e, e.keyCode)
      return
    }

    return false
  })

  // Widgets
  initWidgets()

  // Some special cases...
  $(document.body).on("click", "[data-hours-button]", function() {
    this.blur()
    var value = prompt(this.dataset.hoursButton)
    if (parseFloat(value)) {
      $("#id_days")
        .val((parseFloat(value) / 8).toFixed(2))
        .focus()
    }
  })

  $(document.body).on("click", "[data-multiply-cost]", function() {
    var factor = parseFloat(this.dataset.multiplyCost),
      tpc = parseFloat($("#id_third_party_costs").val()),
      cost = $("#id_cost")

    if (tpc && factor) {
      cost.val(factor * tpc).focus()
    }
  })
})

function initWidgets() {
  $(".datepicker:not(.has-datepicker)")
    .addClass("has-datepicker")
    .datepicker({
      language: "de-DE",
      autoHide: true,
      zIndex: 1500,
    })

  function addZero(num) {
    return num < 10 ? "0" + num : "" + num
  }

  var invoicedOn = $("#id_invoiced_on")
  var dueOn = $("#id_due_on")
  if (invoicedOn.length && dueOn.length) {
    invoicedOn.on("change", function(_event) {
      var due = new Date(
        invoicedOn.datepicker("getDate").getTime() + 14 * 86400 * 1000
      )
      dueOn.val(
        addZero(due.getDate()) +
          "." +
          addZero(1 + due.getMonth()) +
          "." +
          addZero(due.getFullYear())
      )
    })
  }

  $("[data-autofill]:not(.initialized)").each(function() {
    var self = $(this),
      data = self.data("autofill"),
      sel = self.find("select")

    self.addClass("initialized")
    sel.on("change", function() {
      if (data["" + this.value]) {
        $.each(data["" + this.value], function(key, value) {
          self.find("[name$='" + key + "']").val(value)
        })
      }
    })
  })

  $("[data-autocomplete-id]:not(.initialized)").each(function() {
    var self = $(this),
      url = self.data("autocomplete-url"),
      id = self.data("autocomplete-id"),
      input = $("#" + id)

    self
      .addClass("initialized")
      .autocomplete({
        minLength: 3,
        source: function(request, response) {
          $.get(url, {q: request.term}, function(data) {
            response(data.results)
          })
        },
        focus: function(event, ui) {
          self.val(ui.item.label)
          return false
        },
        select: function(event, ui) {
          self.val(ui.item.label)
          input.val(ui.item.value).trigger("change")
          return false
        },
      })
      .on("focus", function() {
        this.select()
      })
  })

  $(document.body).on("click", "[data-clear]", function() {
    $(this.dataset.clear)
      .val("")
      .trigger("change")
  })
}

window.addInlineForm = function addInlineForm(slug, onComplete) {
  var totalForms = $("#id_" + slug + "-TOTAL_FORMS"),
    newId = parseInt(totalForms.val())

  totalForms.val(newId + 1)
  var empty = $("#" + slug + "-empty"),
    attributes = ["id", "name", "for"],
    form = $(empty.html())

  form.removeClass("empty").attr("id", slug + "-" + newId)

  for (var i = 0; i < attributes.length; ++i) {
    var attr = attributes[i]

    form.find("*[" + attr + "*=__prefix__]").each(function() {
      var el = $(this)
      el.attr(attr, el.attr(attr).replace(/__prefix__/, newId))
    })
  }

  // insert the form after the last sibling with the same tagName
  // cannot use siblings() here, because the empty element may be the
  // only one (if no objects exist until now)
  form
    .insertAfter(empty.parent().children("[id|=" + slug + "]:last"))
    .hide()
    .fadeIn()

  if (onComplete) onComplete(form)

  return false
}
