$(function() {

  // AJAX modals
  var initModal = function(data) {
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
    $.post(this.action, $(this).serialize(), function(data, status, jqXHR) {
      if (jqXHR.status === 201) {
        $('.modal').modal('hide');
      } else {
        initModal(data);
      }
    });
    return false;
  });

  // Search forms
  $('.form-search select').on('change', function() {
    $(this).closest('form').submit();
  });

});
