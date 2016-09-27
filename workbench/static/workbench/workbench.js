$(function() {

  // AJAX modals
  var dismissModals = function() {
    // LOL, dismiss.
    $('.modal, .modal-backdrop').remove();
    $(document.body).removeClass('modal-open').removeAttr('style');
  };

  var initModal = function(data) {
    dismissModals();

    $(data).modal();

    if (!('ontouchstart' in document.documentElement)) {
      setTimeout(function() {
        $('.modal').find('input, select').filter(':visible').first().focus();
      }, 500);
    }

    initWidgets();
  };

  $(document.body).on('click', '[data-toggle]', function(event) {
    if (this.dataset.toggle == 'ajaxmodal') {
      event.preventDefault();
      $.get(this.href, function(data) {
        initModal(data);
      });
    }

    var el = $(this.dataset.toggle);
    if (el.length) el.toggleClass('toggled');
  });

  // Include the name and value of the submit button
  $(document.body).on('click', ':submit', function(event) {
    var el = $(this),
      form = el.parents('form');
    form.find('.hidden-submit-value').remove();
    if (!form.length || !el.attr('name')) {
      return;
    }
    form.append(
      $('<input type="hidden" class="hidden-submit-value">').attr({
        name: el.attr('name'),
        value: el.attr('value')
      })
    );
  });

  $(document.body).on('submit', '.modal-dialog form', function(event) {
    if (this.method.toLowerCase() == 'post') {
      $.post(this.action, $(this).serialize(), function(data, status, jqXHR) {
        // 201 CREATED, 202 ACCEPTED or 204 NO CONTENT
        if (jqXHR.status === 201 || jqXHR.status === 202 || jqXHR.status === 204) {
          dismissModals();
          window.location.reload();
        } else {
          initModal(data);
        }
      });
    } else {
      $.get(this.action + '?' + $(this).serialize(), function(data, status, jqXHR) {
        initModal(data);
      });
    }
    return false;
  });

  $(document.body).on('click', '[data-toggle=picker]', function() {
    var el = $(this),
      id = el.data('id'),
      key = el.data('key'),
      pretty = el.data('pretty');

    $('#' + id + '_pretty').val(pretty);
    $('#' + id).val(key).trigger('change');
    dismissModals();
  });

  // Search forms
  $('.form-search').on('change', 'select, input', function() {
    $(this).closest('form').submit();
  });


  // Hotkeys
  $(document.body).on('keydown', function(e) {
    if (/Mac/.test(navigator.platform) ? !e.ctrlKey : !e.altKey) {
      return;
    }

    if (e.keyCode === 70) {  // f
      $('.navbar-form input[name=q]').focus().select();
    } else if (e.keyCode === 72) {  // h
      window.location.href = '/';
    } else if (e.keyCode === 67 && !e.shiftKey) {  // c
      window.location.href = '/contacts/people/';
    } else if (e.keyCode === 67 && e.shiftKey) {  // C
      window.location.href = '/contacts/organizations/';
    } else if (e.keyCode === 80) {  // p
      window.location.href = '/projects/';
    } else if (e.keyCode === 79) {  // o
        window.location.href = '/offers/';
    } else if (e.keyCode === 82) {  // r
      window.location.href = '/invoices/';
    } else if (e.keyCode === 65) {  // a
      window.location.href = '/activities/';
    } else if (e.keyCode === 13) {
      $(e.target).parents('form').submit();
    } else {
      console.log(e, e.keyCode);
      return;
    }

    return false;
  });

  // Widgets
  initWidgets();

});

function initWidgets() {
  $('.datepicker:not(.has-datepicker)').addClass('has-datepicker').datetimepicker({
    locale: 'de',
    format: 'DD.MM.YYYY',
    useCurrent: false,
    showTodayButton: true,
    icons: {
      today: 'glyphicon glyphicon-calendar set-to-today'
    }
  });

  var invoicedOn = $('#id_invoiced_on');
  var dueOn = $('#id_due_on');
  if (invoicedOn.length && dueOn.length) {
      invoicedOn.on('dp.change', function(e) {
          dueOn.val(e.date.add(14, 'days').calendar());
      });
  }

}

function addInlineForm(slug, onComplete) {
  var totalForms = $('#id_' + slug + '-TOTAL_FORMS'),
    newId = parseInt(totalForms.val());

  totalForms.val(newId + 1);
  var empty = $('#' + slug + '-empty'),
    attributes = ['id', 'name', 'for'],
    form = $(empty.html());

  form.removeClass('empty').attr('id', slug + '-' + newId);

  for (var i=0; i<attributes.length; ++i) {
    var attr = attributes[i];

    form.find('*[' + attr + '*=__prefix__]').each(function() {
      var el = $(this);
      el.attr(attr, el.attr(attr).replace(/__prefix__/, newId));
    });
  }

  // insert the form after the last sibling with the same tagName
  // cannot use siblings() here, because the empty element may be the
  // only one (if no objects exist until now)
  form.insertAfter(
    empty.parent().children('[id|=' + slug + ']:last')
    ).hide().fadeIn();

  if (onComplete)
    onComplete(form);

  return false;
};
