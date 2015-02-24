$(function() {

  // AJAX modals
  $(document.body).on('click', '[data-toggle=ajaxmodal]', function(event) {
    $.get(this.href, function(data) {
      $(data).modal();
    });
    return false;
  });

  $(document.body).on('submit', '.modal-dialog form', function() {
    $.post(this.action, $(this).serialize(), function(data, status, jqXHR) {
      if (jqXHR.status === 201) {
        $('.modal').modal('hide');
      } else {
        $(data).modal();
      }
    });
    return false;
  });

  // Search forms
  $('.form-search select').on('change', function() {
    $(this).closest('form').submit();
  });

});
