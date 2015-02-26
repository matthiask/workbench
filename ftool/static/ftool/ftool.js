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
