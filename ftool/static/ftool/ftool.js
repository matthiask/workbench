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
    $('#' + id + '_pretty').text(pretty);
    $('.modal').modal('hide');
  });

  // Search forms
  $('.form-search select').on('change', function() {
    $(this).closest('form').submit();
  });

});
