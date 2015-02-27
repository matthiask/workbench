$(function() {

  // AJAX modals
  var initModal = function(data) {
    $('.modal').modal('hide');
    $(data).modal();
    setTimeout(function() {
      $('.modal').find('input, select').filter(':visible').first().focus();
    }, 500);
  };
  $(document.body).on('click', '[data-toggle=ajaxmodal]', function(event) {
    $('.modal').remove();

    $.get(this.href, function(data) {
      initModal(data);
    });
    return false;
  });

  $(document.body).on('submit', '.modal-dialog form', function() {
    if (this.method.toLowerCase() == 'post') {
      $.post(this.action, $(this).serialize(), function(data, status, jqXHR) {
        if (jqXHR.status === 201) {
          $('.modal').modal('hide');
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

    $('#' + id).val(key);
    $('#' + id + '_pretty').val(pretty);
    $('.modal').modal('hide');
  });

  // Search forms
  $('.form-search select').on('change', function() {
    $(this).closest('form').submit();
  });


  // Hotkeys
  $(document.body).on('keyup', function(e) {
    if (/Mac/.test(navigator.platform) ? !e.ctrlKey : !e.altKey) {
      return;
    }

    if (e.keyCode === 70) {  // f
      $('.navbar-form input[name=q]').focus().select();
    } else if (e.keyCode === 67 && !e.shiftKey) {  // c
      window.location.href = '/contacts/people/';
    } else if (e.keyCode === 67 && e.shiftKey) {  // C
      window.location.href = '/contacts/organizations/';
    } else if (e.keyCode === 13) {
      $(e.target).parents('form').submit();
    } else {
      console.log(event, event.keyCode);
      return;
    }

    return false;
  });

});

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
